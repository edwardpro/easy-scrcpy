"""Temporary IP discovery and asynchronous targeted ADB wireless operations."""

from collections import namedtuple
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import re
import secrets
import string
import threading
import time

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .core import parse_devices, resolve_executable
from .runtime import tool_environment
from .i18n import tr

PHASE_TIMEOUT_MS = 20000
VERIFY_ATTEMPTS = 8
QR_WAIT_ATTEMPTS = 180  # ~3 minutes for the user to open the scanner and scan

MdnsService = namedtuple("MdnsService", "name kind address")


def endpoint(host, port):
    address = ipaddress.ip_address(str(host).strip())
    number = int(str(port).strip())
    if not 1 <= number <= 65535 or address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError("Invalid IP address or port")
    return f"[{address}]:{number}" if address.version == 6 else f"{address}:{number}"


def new_pairing_credentials():
    """Alphanumeric only: ADB QR fields must otherwise be backslash-escaped."""
    alphabet = string.ascii_letters + string.digits
    name = "easyscrcpy-" + "".join(secrets.choice(alphabet) for _ in range(8))
    password = "".join(secrets.choice(alphabet) for _ in range(12))
    return name, password


def pairing_qr_payload(name, password):
    """Format parsed by Android Settings (AdbQrCode): WIFI:T:ADB;S:<name>;P:<password>;;"""
    if not re.fullmatch(r"[A-Za-z0-9-]+", name) or not re.fullmatch(r"[A-Za-z0-9]+", password):
        raise ValueError("Invalid pairing credentials")
    return f"WIFI:T:ADB;S:{name};P:{password};;"


def parse_mdns(output):
    """Parse `adb mdns services` (instance, service type, IP:port per line)."""
    kinds = {"_adb-tls-pairing._tcp": "pairing", "_adb-tls-connect._tcp": "connect"}
    services = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 3 or fields[1].rstrip(".") not in kinds:
            continue
        match = re.fullmatch(r"(?:\[([^]]+)\]|([^:]+)):(\d+)", fields[2])
        if not match:
            continue
        try:
            address = endpoint(match[1] or match[2], match[3])
        except ValueError:
            continue
        services.append(MdnsService(fields[0], kinds[fields[1].rstrip(".")], address))
    return services


def classify_failure(output):
    """Map ADB's free-form error text to an actionable, translated hint."""
    text = output.lower()
    if "not scanned" in text:
        return "qr_timeout"
    if "not advertised over mdns" in text:
        return "mdns"
    if any(s in text for s in ("no route to host", "host is down", "network is unreachable")):
        return "network"
    if "connection refused" in text:
        return "refused"
    if "wrong password" in text or "pairing code" in text and "failed" in text:
        return "code"
    if "failed to authenticate" in text or "unauthorized" in text:
        return "authorize"
    return "unknown"


FAILURE_HINTS = {
    "qr_timeout": "未检测到扫码配对：请确认手机已在“无线调试 → 使用二维码配对设备”中扫描，且电脑与手机在同一 Wi-Fi。若网络屏蔽组播（mDNS），请改用配对码。",
    "mdns": "未发现该设备：请确认手机已开启无线调试、与电脑在同一 Wi-Fi；若网络屏蔽组播（mDNS），请手动填写 IP 和连接端口。",
    "network": "网络不可达：确认电脑与手机在同一非访客 Wi-Fi，手机亮屏且无线调试仍开启。macOS 请在“系统设置 → 隐私与安全性 → 本地网络”允许 EasyScrcpy；若 ADB 服务由终端或其他工具启动，也需允许该应用，或退出这些工具后重试。",
    "refused": "端口被拒绝：无线调试可能已关闭或端口已变化，请重新查看手机无线调试页面的 IP 地址和端口。",
    "code": "配对失败：配对码错误或已过期。请在手机上重新打开“使用配对码配对设备”，填写新的配对端口和配对码。",
    "authorize": "设备尚未授权此电脑：请先“首次配对”。",
    "adb_network": "电脑可以访问手机，但 ADB 服务无法访问局域网：ADB 服务可能由终端或其他工具启动，缺少 macOS 本地网络权限。可点击“重启 ADB 服务”，由 EasyScrcpy 重新启动后重试。",
    "unknown": "连接失败：若此电脑尚未与手机配对，请先“首次配对”；否则请检查 IP、端口及手机无线调试状态。",
}


class Discovery(QObject):
    candidate = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = None
        self.thread = None
        self.generation = 0
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.stop)

    def start(self, host):
        self.stop()
        address = ipaddress.ip_address(host.strip())
        if address.version != 4 or not address.is_private or address.is_loopback or address.is_unspecified:
            raise ValueError("Select a LAN IPv4 address")
        token = secrets.token_urlsafe(32)
        generation = self.generation
        owner = self
        steps = [tr(step) for step in (
            "在手机打开“设置 → 开发者选项”（未开启时：关于手机 → 连续点按版本号 7 次）。",
            "打开“无线调试”，允许当前 Wi-Fi 网络。",
            "首次使用：在电脑上选择“首次配对”，然后在手机点“使用二维码配对设备”扫描电脑上的配对二维码。",
            "无线调试主页面显示“IP 地址和端口”，冒号后为连接端口；若电脑未能自动发现，请在电脑上填写该端口。",
        )]
        title = tr("网页无法读取调试端口，请按以下步骤在电脑上填写：")
        expires = time.monotonic() + 300
        accepted = threading.Event()
        candidate_lock = threading.Lock()

        class Server(ThreadingHTTPServer):
            def process_request(self, request, client_address):
                if not self.slots.acquire(blocking=False):
                    request.close()
                    return
                super().process_request(request, client_address)

            def process_request_thread(self, request, client_address):
                try:
                    request.settimeout(3)
                    super().process_request_thread(request, client_address)
                finally:
                    self.slots.release()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/" + token or time.monotonic() >= expires:
                    self.send_error(404)
                    return
                host = escape(self.client_address[0])
                items = "".join(f"<li>{escape(step)}</li>" for step in steps)
                data = ("<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                        "<title>Easy Scrcpy</title><h1>Easy Scrcpy</h1>"
                        f"<p><b>IP: {host}</b></p><p>{escape(title)}</p><ol>{items}</ol>").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                with candidate_lock:
                    if generation == owner.generation and not accepted.is_set():
                        accepted.set()
                        owner.candidate.emit(self.client_address[0])

            def log_message(self, *args):
                pass

        self.server = Server((str(address), 0), Handler)
        self.server.slots = threading.BoundedSemaphore(8)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self.thread.start()
        self.deadline.start(300000)
        return f"http://{address}:{self.server.server_port}/{token}"

    def stop(self):
        self.deadline.stop()
        self.generation += 1
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=1)
            self.server = None


class WirelessConnection(QObject):
    """Wireless ADB flows. Every step is a separate, timed `adb` process.

    QR pairing:    mdns(pairing service S) -> pair -> locate(guid)
    Pairing code:  pair -> locate(guid / optional connect port)
    Paired device: locate(guid) -> mdns(connect service) -> connect -> locate
    IP connection: connect -> locate(IP:port)
    """

    status = Signal(str)
    connected = Signal(str, str, str, str)  # serial, guid, model, address
    disconnected = Signal(str)
    failure = Signal(str, str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._timeout)
        self.retry = QTimer(self)
        self.retry.setSingleShot(True)
        self.retry.timeout.connect(self._retry)
        self._reset()

    def _reset(self):
        self.phase = ""
        self.next_phase = ""
        self.target = ""
        self.guid = ""
        self.pair_name = ""
        self.code = ""
        self.connect_tried = False
        self.attempts = 0

    def busy(self):
        return bool(self.phase) or self.retry.isActive() or self.process.state() != QProcess.ProcessState.NotRunning

    def _begin(self):
        if self.busy():
            raise ValueError("Operation already in progress")
        self._reset()

    def pair_qr(self, name, password):
        """Wait for the phone to scan `pairing_qr_payload(name, password)`."""
        self._begin()
        self.pair_name, self.code = name, password
        self._mdns("find_pairing")

    def connect_device(self, host, port=None, pair_port=None, code=""):
        """Pairing code (connection port optional) or plain IP:port connection."""
        self._begin()
        if pair_port is None and port in (None, ""):
            raise ValueError("Connection port required")
        target = endpoint(host, port) if port not in (None, "") else ""
        if pair_port is not None:
            if not code.isascii() or not code.isdigit() or len(code) != 6:
                raise ValueError("Pairing code must contain six digits")
            pairing = endpoint(host, pair_port)
            if pairing == target:
                raise ValueError("Pairing port and connection port must differ")
        self.target = target
        if pair_port is not None:
            # ADB accepts the code as an argument (documented `pair HOST:PORT CODE`);
            # the interactive prompt is not reliable through a GUI pipe.
            self.code = code
            self._run("pair", ["pair", pairing, code])
        else:
            self.connect_tried = True
            self._run("connect", ["connect", self.target])

    def connect_paired(self, guid):
        """Reconnect a known device: ADB auto-connect or mDNS gives the current port."""
        self._begin()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", guid):
            raise ValueError("Invalid device id")
        self.guid = guid
        self._locate()

    def restart_server(self):
        """Only after explicit user confirmation: affects every ADB client and device."""
        self._begin()
        self._run("kill", ["kill-server"])

    def disconnect_device(self, serial):
        self._begin()
        # ADB can enumerate TLS transports by mDNS name rather than IP:port.
        if not re.fullmatch(r"[A-Za-z0-9_.-]+\._adb-tls-connect\._tcp\.?", serial):
            match = re.fullmatch(r"(?:\[([^]]+)\]|([^:]+)):(\d+)", serial)
            if not match:
                raise ValueError("Invalid wireless transport")
            endpoint(match[1] or match[2], match[3])
        self.target = serial
        self._run("disconnect", ["disconnect", serial])

    def _run(self, phase, arguments):
        adb = resolve_executable("adb", self.settings.adb_path)
        if not adb:
            self.phase = ""
            self.code = ""
            raise ValueError("ADB not found")
        self.phase = phase
        self.process.setProgram(adb)
        self.process.setArguments(arguments)
        self.process.setProcessEnvironment(tool_environment())
        self.timer.start(PHASE_TIMEOUT_MS)
        self.status.emit(phase)
        self.process.start()

    def _mdns(self, phase):
        self._advance(phase, ["mdns", "services"])

    def _locate(self):
        self._advance("locate", ["devices", "-l"])

    def _sanitize(self, text):
        if self.code:
            text = text.replace(self.code, "******")
        return text.strip()[-1500:]

    def _fail(self, output):
        detail = self._sanitize(output)
        self.code = ""
        self.status.emit("failed")
        self.failure.emit(classify_failure(detail), detail)

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.timer.stop()
            self.phase = ""
            self._fail(self.process.errorString())

    def _schedule(self, phase, delay):
        self.next_phase = phase
        self.retry.start(delay)

    def _retry(self):
        phase, self.next_phase = self.next_phase, ""
        if phase == "locate":
            self._locate()
        elif phase:
            self._mdns(phase)

    def _finished(self, code, status):
        self.timer.stop()
        phase = self.phase
        self.phase = ""
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        if not phase:
            return
        text = output.lower()
        ok = code == 0 and status == QProcess.ExitStatus.NormalExit
        if phase == "find_pairing":
            address = next((s.address for s in parse_mdns(output)
                            if s.name == self.pair_name and s.kind == "pairing"), None)
            if address:
                self._advance("pair", ["pair", address, self.code])
            elif self.attempts < QR_WAIT_ATTEMPTS:
                self.attempts += 1
                self._schedule("find_pairing", 1000)
            else:
                self._fail("pairing QR code was not scanned in time")
        elif phase == "pair":
            match = re.search(r"guid=([A-Za-z0-9_.-]+)", output)
            if ok and "successfully paired" in text:
                self.code = ""
                self.guid = match[1] if match else ""
                self.attempts = 0
                # ADB auto-connects known hosts advertised over mDNS shortly after pairing.
                self._schedule("locate", 500)
            else:
                self._fail(output)
        elif phase == "locate":
            self._located(output, ok)
        elif phase == "find_connect":
            address = next((s.address for s in parse_mdns(output)
                            if s.name == self.guid and s.kind == "connect"), None)
            if address:
                self.target = address
                self.connect_tried = True
                self._advance("connect", ["connect", address])
            else:
                self._wait_or_fail(output or "device not advertised over mDNS")
        elif phase == "connect":
            # `adb connect` exits 0 even on failure; inspect the server response.
            failed = any(s in text for s in ("failed", "unable", "cannot", "refused", "no route"))
            if ok and re.search(r"\bconnected to\b", text) and not failed:
                self._schedule("locate", 300)
            else:
                self._fail(output)
        elif phase == "kill":
            # kill-server reports success even when no server was running.
            self._advance("start", ["start-server"])
        elif phase == "start":
            if ok:
                self.status.emit("restarted")
            else:
                self._fail(output)
        elif phase == "disconnect":
            if ok and "disconnected" in text and "failed" not in text:
                self.status.emit("disconnected")
                self.disconnected.emit(self.target)
            else:
                self._fail(output)

    def _located(self, output, ok):
        def matches(device):
            return (self.target and device.serial == self.target) or (
                self.guid and device.serial.startswith(self.guid + "."))
        device = next((d for d in parse_devices(output) if matches(d)), None) if ok else None
        if device and device.state == "device":
            address = self.target or ""
            self.status.emit("connected")
            self.connected.emit(device.serial, self.guid, device.model, address)
        elif device and device.state == "unauthorized":
            self._fail("unauthorized")
        elif self.target and not self.connect_tried:
            self.connect_tried = True
            self._advance("connect", ["connect", self.target])
        elif self.guid and not self.target:
            self._mdns("find_connect")
        else:
            self._wait_or_fail(output or "device not ready")

    def _wait_or_fail(self, output):
        if self.attempts < VERIFY_ATTEMPTS:
            self.attempts += 1
            self._schedule("locate", 1000)
        else:
            self._fail(output)

    def _advance(self, phase, args):
        try:
            self._run(phase, args)
        except (ValueError, OSError) as error:
            self._fail(str(error))

    def _timeout(self):
        self.cancel()
        self.status.emit("timeout")

    def cancel(self):
        self.timer.stop()
        self.retry.stop()
        self.phase = ""
        self.next_phase = ""
        self.code = ""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        self.status.emit("cancelled")

    def shutdown(self):
        self.cancel()
        self.process.waitForFinished(1000)
