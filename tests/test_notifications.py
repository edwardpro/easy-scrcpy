import unittest
from unittest.mock import patch

from easy_scrcpy.core import Device
from easy_scrcpy.notifications import DeviceNotifications
from test_qt import APP


class FakeBackend:
    def __init__(self):
        self.shown, self.removed = [], []

    def show(self, token, name, actions):
        self.shown.append((token, name, actions))

    def remove(self, token):
        self.removed.append(token)

    def close(self):
        pass


class NotificationTests(unittest.TestCase):
    def test_per_device_actions_and_stale_tokens(self):
        with patch("easy_scrcpy.notifications.sys.platform", "linux"):
            notifications = DeviceNotifications()
        backend = FakeBackend()
        notifications.backend = backend
        actions = []
        notifications.action.connect(lambda serial, action: actions.append((serial, action)))
        a, b = Device("a", "device", "Pixel_8", True), Device("b", "device", "Pixel_9", True)
        notifications.sync([a, b, Device("c", "unauthorized", usb=True)])
        notifications.sync([a, b])
        self.assertEqual(len(backend.shown), 2)
        self.assertEqual(backend.shown[0][1], "Pixel 8")
        self.assertEqual([a for a, _ in backend.shown[0][2]], ["restart", "stop", "settings"])
        old_token = notifications.devices["a"]
        notifications._activation.emit(old_token, "restart")
        APP.processEvents()
        self.assertEqual(actions, [("a", "restart")])
        notifications.sync([b])
        self.assertIn(old_token, backend.removed)
        notifications.sync([a, b])
        notifications._dispatch(old_token, "stop")
        self.assertEqual(actions, [("a", "restart")])
        notifications.shutdown()
        self.assertFalse(notifications.devices)

    def test_backend_failure_does_not_break_device_detection(self):
        with patch("easy_scrcpy.notifications.sys.platform", "linux"):
            notifications = DeviceNotifications()
        backend = FakeBackend()
        notifications.backend = backend
        logs = []
        notifications.log.connect(logs.append)
        with patch.object(backend, "show", side_effect=RuntimeError("denied")):
            notifications.sync([Device("a", "device", usb=True)])
        self.assertEqual(len(logs), 1)
        notifications.shutdown()
