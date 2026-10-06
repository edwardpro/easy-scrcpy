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

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.processes: dict[str, QProcess] = {}
        self.stopping: set[str] = set()
        self.output: dict[str, deque[str]] = {}
        self.shutting_down = False

    def start(self, device: Device):
        if device.serial in self.processes:
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
            self.stopping.discard(serial)
            self.output.pop(serial, None)
        # Release closures retaining the QProcess wrapper before deferred deletion.
        process.readyReadStandardOutput.disconnect()
        process.finished.disconnect()
        process.errorOccurred.disconnect()
        process.deleteLater()
        self.changed.emit()

    def stop(self, serial: str):
        process = self.processes.get(serial)
        if process is None or serial in self.stopping:
            return
        self.stopping.add(serial)
        process.terminate()
        # A context-bound timer cannot fire after this process has been deleted.
        timer = QTimer(process)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: process.kill() if process.state() != QProcess.ProcessState.NotRunning else None)
        timer.start(2000)
        self.changed.emit()

    def stop_all(self):
        for serial in list(self.processes):
            self.stop(serial)

    def shutdown(self):
        self.shutting_down = True
        processes = list(self.processes.values())
        self.stop_all()
        for process in processes:
            if process.state() != QProcess.ProcessState.NotRunning:
                if not process.waitForFinished(1500):
                    process.kill()
                    process.waitForFinished(1000)
