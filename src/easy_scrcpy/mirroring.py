from collections import deque
import os
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .core import Device, Settings, resolve_executable, scrcpy_arguments
from .runtime import tool_environment
from .i18n import tr


class MirroringManager(QObject):
    changed = Signal()
    error = Signal(str)
    log = Signal(str)
    restart_ready = Signal(object)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.processes: dict[str, QProcess] = {}
        self.stopping: set[str] = set()
        self.terminating: set[str] = set()
        self.debug_commands: dict[str, QProcess] = {}
        self.restarts: dict[str, Device] = {}
        self.usb_devices: set[str] = set()
        self.output: dict[str, deque[str]] = {}
        self.shutting_down = False

    def start(self, device: Device):
        if device.serial in self.processes or device.serial in self.debug_commands:
            return
        if device.state != "device":
            self.error.emit(tr("设备尚未就绪，请在手机上开启 USB 调试并确认授权。"))
            return
        executable = resolve_executable("scrcpy", self.settings.scrcpy_path)
        adb = resolve_executable("adb", self.settings.adb_path)
        if not executable or not adb:
            self.error.emit(tr("找不到 scrcpy 或 ADB：请检查应用包是否完整，或在设置中指定外部路径。"))
            return
        process = QProcess(self)
        process.setProgram(executable)
        process.setArguments(scrcpy_arguments(device, self.settings))
        environment = tool_environment()
        environment.insert("ADB", adb)
        environment.insert("PATH", str(Path(adb).parent) + os.pathsep + environment.value("PATH"))
        server = Path(executable).parent / "scrcpy-server"
        if server.is_file():
            environment.insert("SCRCPY_SERVER_PATH", str(server))
        # Do not inherit a global server override for a different scrcpy version.
        elif not self.settings.scrcpy_path:
            environment.remove("SCRCPY_SERVER_PATH")
        process.setProcessEnvironment(environment)
        process.setWorkingDirectory(str(Path(executable).parent))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        serial = device.serial
        if device.usb:
            self.usb_devices.add(serial)
        else:
            self.usb_devices.discard(serial)
        self.processes[serial] = process
        self.output[serial] = deque(maxlen=40)
        process.readyReadStandardOutput.connect(lambda: self._read(serial, process))
        process.finished.connect(lambda code, status: self._finished(serial, process, code, status))
        process.errorOccurred.connect(lambda error: self._error(serial, process, error))
        process.start()
        self.changed.emit()

    def _read(self, serial, process):
        text = bytes(process.readAllStandardOutput()).decode("utf-8", "replace")
        if text:
            self.output.get(serial, deque(maxlen=40)).extend(text.splitlines())
            self.log.emit(f"[{serial}] {text.rstrip()}")

    def _error(self, serial, process, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.error.emit(tr("无法启动 scrcpy ({serial})：{error}", serial=serial, error=process.errorString()))
            self._cleanup(serial, process)

    def _finished(self, serial, process, code, status):
        self._read(serial, process)
        if (code != 0 or status == QProcess.ExitStatus.CrashExit) and serial not in self.stopping and not self.shutting_down:
            tail = "\n".join(self.output.get(serial, []))[-4000:]
            self.error.emit(tr("投屏异常退出 ({serial})，退出码 {code}\n{output}", serial=serial, code=code, output=tail))
        self._cleanup(serial, process)

    def _cleanup(self, serial, process):
        if self.processes.get(serial) is process:
            self.processes.pop(serial)
            if serial not in self.debug_commands:
                self.stopping.discard(serial)
            self.terminating.discard(serial)
            self.output.pop(serial, None)
        # Release closures retaining the QProcess wrapper before deferred deletion.
        process.readyReadStandardOutput.disconnect()
        process.finished.disconnect()
        process.errorOccurred.disconnect()
        process.deleteLater()
        self.changed.emit()
        device = self.restarts.pop(serial, None)
        if device is not None and not self.shutting_down:
            self.restart_ready.emit(device)

    def stop(self, serial: str, *, restarting=False):
        if not restarting:
            self.restarts.pop(serial, None)
        process = self.processes.get(serial)
        if process is None or serial in self.terminating:
            return
        self.stopping.add(serial)
        self.terminating.add(serial)
        process.terminate()
        # A context-bound timer cannot fire after this process has been deleted.
        timer = QTimer(process)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: process.kill() if process.state() != QProcess.ProcessState.NotRunning else None)
        timer.start(2000)
        self.changed.emit()

    def restart(self, device: Device):
        if device.serial not in self.processes or device.serial in self.stopping:
            return
        self.restarts[device.serial] = device
        # Quality changes must never go through request_stop / disable USB debugging.
        self.stop(device.serial, restarting=True)

    def request_stop(self, serial: str):
        """Manual stop only. Disconnect and shutdown use stop() directly."""
        mirror = self.processes.get(serial)
        if mirror is None or serial in self.stopping:
            return
        if not self.settings.disable_debug_on_stop or serial not in self.usb_devices:
            self.stop(serial)
            return
        adb = resolve_executable("adb", self.settings.adb_path)
        if not adb:
            self.stop(serial)
            self.error.emit(tr("无法关闭 USB 调试 ({serial})：找不到 ADB；仍会停止投屏。", serial=serial))
            return
        self.stopping.add(serial)
        command = QProcess(self)
        command.setProgram(adb)
        command.setArguments(["-s", serial, "shell", "settings", "put", "global", "adb_enabled", "0"])
        command.setProcessEnvironment(tool_environment())
        command.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.debug_commands[serial] = command
        timer = QTimer(command)
        timer.setSingleShot(True)
        timed_out = False

        def complete(code, status):
            if self.debug_commands.get(serial) is not command:
                return
            timer.stop()
            output = bytes(command.readAllStandardOutput()).decode("utf-8", "replace").strip()[-2000:]
            self.debug_commands.pop(serial)
            command.finished.disconnect()
            command.errorOccurred.disconnect()
            timer.timeout.disconnect()
            command.deleteLater()
            failed = timed_out or code != 0 or status != QProcess.ExitStatus.NormalExit or bool(output)
            if self.processes.get(serial) is mirror:
                self.stop(serial)
            elif serial not in self.processes:
                self.stopping.discard(serial)
            self.changed.emit()
            if failed:
                self.error.emit(tr("无法确认 USB 调试已关闭 ({serial})：{error}；仍会停止投屏。请在手机上检查。",
                                   serial=serial, error=tr("请求超时") if timed_out else output or command.errorString()))
            else:
                self.log.emit(tr("已发送关闭 USB 调试请求 ({serial})；请在手机上确认，下次投屏需手动开启。", serial=serial))

        def timeout():
            nonlocal timed_out
            timed_out = True
            command.kill()

        def error(reason):
            if reason == QProcess.ProcessError.FailedToStart:
                complete(-1, QProcess.ExitStatus.CrashExit)

        command.finished.connect(complete)
        command.errorOccurred.connect(error)
        timer.timeout.connect(timeout)
        timer.start(3000)
        self.log.emit(tr("正在尝试关闭 USB 调试 ({serial})…", serial=serial))
        command.start()
        self.changed.emit()

    def request_stop_all(self):
        for serial in list(self.processes):
            self.request_stop(serial)

    def stop_all(self):
        for serial in list(self.processes):
            self.stop(serial)

    def shutdown(self):
        self.shutting_down = True
        self.restarts.clear()
        for serial, command in list(self.debug_commands.items()):
            self.debug_commands.pop(serial)
            command.finished.disconnect()
            command.errorOccurred.disconnect()
            for timer in command.findChildren(QTimer):
                timer.stop()
                timer.timeout.disconnect()
            command.kill()
            command.waitForFinished(1000)
            command.deleteLater()
            if serial not in self.processes:
                self.stopping.discard(serial)
        processes = list(self.processes.values())
        self.stop_all()
        for process in processes:
            if process.state() != QProcess.ProcessState.NotRunning:
                if not process.waitForFinished(1500):
                    process.kill()
                    process.waitForFinished(1000)
