"""Read-only, asynchronous ADB server protocol probe."""
import re

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QTcpSocket

from .runtime import tool_environment


def server_endpoint(environment):
    spec = environment.value("ADB_SERVER_SOCKET")
    if spec:
        match = re.fullmatch(r"tcp:(?:\[([^]]+)\]|([^:]+)):(\d+)", spec)
        if not match:
            raise ValueError("Unsupported ADB_SERVER_SOCKET")
        host, port = match[1] or match[2], int(match[3])
    else:
        host = environment.value("ANDROID_ADB_SERVER_ADDRESS") or "localhost"
        port = int(environment.value("ANDROID_ADB_SERVER_PORT") or "5037")
    if not host or not 1 <= port <= 65535:
        raise ValueError("Invalid ADB server endpoint")
    return host, port


class AdbServerProbe(QObject):
    result = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.socket.connected.connect(lambda: self.socket.write(b"000Chost:version"))
        self.socket.readyRead.connect(self._read)
        self.socket.errorOccurred.connect(lambda *_: self._finish(False))
        self.timer.timeout.connect(lambda: self._finish(False))
        self.active = False
        self.address = ""

    def check(self):
        self.stop()
        self.buffer = b""
        self.address = ""
        self.active = True
        try:
            host, port = server_endpoint(tool_environment())
        except ValueError:
            self._finish(False)
            return
        self.address = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
        self.timer.start(3000)
        self.socket.connectToHost(host, port)

    def _read(self):
        self.buffer += bytes(self.socket.readAll())
        if len(self.buffer) < 4:
            return
        if self.buffer[:4] != b"OKAY":
            self._finish(False)
        elif len(self.buffer) >= 8:
            try:
                length = int(self.buffer[4:8], 16)
            except ValueError:
                self._finish(False)
                return
            if length != 4:
                self._finish(False)
            elif len(self.buffer) >= 12:
                self._finish(bool(re.fullmatch(rb"[0-9a-fA-F]{4}", self.buffer[8:12])))

    def _finish(self, available):
        if not self.active:
            return
        self.stop()
        self.result.emit(available, self.address)

    def stop(self):
        self.active = False
        self.timer.stop()
        self.socket.abort()
