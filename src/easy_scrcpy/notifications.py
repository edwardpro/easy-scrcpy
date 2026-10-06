"""Actionable native device notifications, with optional platform backends."""

import sys
import uuid

from PySide6.QtCore import QObject, Qt, Signal

from .i18n import tr


class DeviceNotifications(QObject):
    action = Signal(str, str)
    log = Signal(str)
    _activation = Signal(str, str)
    _failure = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.devices = {}
        self.backend = None
        self._activation.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        self._failure.connect(self.log, Qt.ConnectionType.QueuedConnection)
        try:
            if sys.platform == "win32":
                from .notifications_windows import WindowsNotifications
                self.backend = WindowsNotifications(self._activation.emit, self._failure.emit)
            elif sys.platform == "darwin":
                from .notifications_macos import MacNotifications
                self.backend = MacNotifications(self._activation.emit, self._failure.emit)
        except Exception as error:
            # Native notification support must never prevent launching the GUI.
            self._failure.emit(tr("设备通知不可用：{error}", error=error))

    def sync(self, devices):
        current = {d.serial: d for d in devices if d.state == "device"}
        for serial in list(self.devices):
            if serial not in current:
                self.remove(serial)
        if self.backend is None:
            return
        for serial, device in current.items():
            if serial in self.devices:
                continue
            # A random token prevents an old notification from controlling a
            # newly connected device with the same serial.
            token = uuid.uuid4().hex
            self.devices[serial] = token
            try:
                self.backend.show(token, device.model.replace("_", " "),
                                  [("restart", tr("重新投屏")), ("stop", tr("停止投屏")), ("settings", tr("设置"))])
            except Exception as error:
                self.log.emit(tr("设备通知不可用：{error}", error=error))

    def _dispatch(self, token, action):
        serial = next((s for s, t in self.devices.items() if t == token), None)
        if serial is not None and action in {"restart", "stop", "settings"}:
            self.action.emit(serial, action)

    def remove(self, serial):
        token = self.devices.pop(serial, None)
        if token and self.backend:
            try:
                self.backend.remove(token)
            except Exception as error:
                self.log.emit(tr("设备通知不可用：{error}", error=error))

    def refresh_language(self, devices):
        for serial in list(self.devices):
            self.remove(serial)
        self.sync(devices)

    def request_permission(self):
        if self.backend:
            try:
                self.backend.request_permission()
                if sys.platform == "win32":
                    # Windows permissions are changed in system Settings.
                    for serial in list(self.devices):
                        self.remove(serial)
            except Exception as error:
                self.log.emit(tr("设备通知不可用：{error}", error=error))

    def shutdown(self):
        for serial in list(self.devices):
            self.remove(serial)
        if self.backend:
            self.backend.close()
