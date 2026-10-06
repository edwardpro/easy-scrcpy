from dataclasses import replace

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .core import Device, Settings, is_network_or_emulator, parse_devices, resolve_executable
from .runtime import tool_environment
from .i18n import tr


class DeviceMonitor(QObject):
    snapshot = Signal(list)
    health = Signal(str)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.process = QProcess(self)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.scan)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self._timeout)
        self.active = False
        self.stopped = False
        self.failed = False
        self.phase = ""
        self.pending: list[Device] = []
        self.devices: list[Device] = []
        self.resolving: Device | None = None

    def start(self):
        self.timer.start()
        self.scan()

    def scan(self):
        if self.active or self.stopped:
            return
        self.adb = resolve_executable("adb", self.settings.adb_path)
        if not self.adb:
            self.health.emit(tr("找不到 ADB：内置依赖可能缺失，请重新安装应用或在设置中指定路径。"))
            return
        self.active = True
        self.devices = []
        self.phase = "list"
        self._run(["devices", "-l"])

    def _run(self, arguments):
        self.failed = False
        self.process.setProgram(self.adb)
        self.process.setProcessEnvironment(tool_environment())
        self.process.setArguments(arguments)
        self.deadline.start(5000)
        self.process.start()

    def _timeout(self):
        self.failed = True
        self.health.emit(tr("ADB 查询超时；保留上次设备状态，稍后重试。"))
        self.process.kill()

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.deadline.stop()
            self.active = False
            self.health.emit(tr("无法启动 ADB：{error}", error=self.process.errorString()))

    def _finished(self, code, status):
        self.deadline.stop()
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        error = bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
        if self.stopped:
            return
        if self.failed or code != 0 or status != QProcess.ExitStatus.NormalExit:
            self.active = False
            if not self.failed:
                self.health.emit(tr("ADB 查询失败：{error}", error=error.strip() or code))
            # Never treat a failed query as all devices being unplugged.
            return
        if self.phase == "list":
            self.pending = parse_devices(output)
        elif self.resolving is not None:
            if output.strip().startswith("usb:"):
                self.devices.append(replace(self.resolving, usb=True))
        self._next()

    def _next(self):
        while self.pending:
            device = self.pending.pop(0)
            if device.usb:
                self.devices.append(device)
            elif not is_network_or_emulator(device.serial):
                # Some hosts omit usb: metadata in `devices -l`.
                self.phase = "path"
                self.resolving = device
                self._run(["-s", device.serial, "get-devpath"])
                return
        self.active = False
        self.health.emit("正在监听 USB Android 设备")
        self.snapshot.emit(self.devices)

    def stop(self):
        self.stopped = True
        self.timer.stop()
        self.deadline.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(1000)
