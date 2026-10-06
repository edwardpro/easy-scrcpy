import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

from easy_scrcpy.app import Controller, set_macos_foreground
from easy_scrcpy.core import Settings
from easy_scrcpy.monitor import DeviceMonitor
from test_qt import APP


class MacForegroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        APP.processEvents()
        self.temp.cleanup()

    def test_offscreen_and_other_platforms_are_noop(self):
        with patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}):
            self.assertIsNone(set_macos_foreground(True))
        environment = {key: value for key, value in os.environ.items() if key != "QT_QPA_PLATFORM"}
        with patch("easy_scrcpy.app.sys.platform", "linux"), patch.dict(os.environ, environment, clear=True):
            self.assertIsNone(set_macos_foreground(True))

    def test_show_window_activates_and_close_to_tray_deactivates(self):
        with patch.object(DeviceMonitor, "start"), patch(
                "easy_scrcpy.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False), patch(
                "easy_scrcpy.app.set_macos_foreground") as foreground:
            controller = Controller(APP, self.path / "settings.json",
                                    Settings(language="zh"), background=True)
            try:
                # Tray unavailable keeps the window open, so init already showed it.
                self.assertEqual(foreground.call_args_list, [call(True)])
                self.assertTrue(controller.window.isVisible())
                controller.window.tray_available = True
                controller.window.close()
                self.assertEqual(foreground.call_args_list, [call(True), call(False)])
                self.assertFalse(controller.window.isVisible())
                controller.show_window()
                self.assertEqual(foreground.call_args_list[-1], call(True))
            finally:
                controller.cleanup()
                controller.window.hide()
                controller.deleteLater()


@unittest.skipIf(sys.platform != "darwin", "macOS UserNotifications")
class MacNotificationContentTests(unittest.TestCase):
    def test_per_device_thread_sound_and_permission(self):
        import easy_scrcpy.notifications_macos as mod
        UN = MagicMock()
        UN.UNAuthorizationStatusAuthorized = 1
        UN.UNAuthorizationStatusProvisional = 2
        UN.UNAuthorizationOptionAlert = 4
        UN.UNAuthorizationOptionSound = 2
        settings = MagicMock()
        settings.authorizationStatus.return_value = 1
        center = UN.UNUserNotificationCenter.currentNotificationCenter.return_value
        center.getNotificationSettingsWithCompletionHandler_.side_effect = lambda handler: handler(settings)
        bundle = MagicMock()
        bundle.bundleIdentifier.return_value = "io.easy-scrcpy.app"
        failures = []
        with patch.object(mod, "UN", UN), patch.object(mod, "NSBundle") as NSBundle, patch.object(
                mod, "NotificationDelegate"), patch.object(sys, "frozen", True, create=True):
            NSBundle.mainBundle.return_value = bundle
            backend = mod.MacNotifications(lambda token, action: None, failures.append)
            backend.show("token-a", "Pixel 8", [("restart", "Restart")])
            backend.show("token-b", "Pixel 9", [("restart", "Restart")])
            backend.request_permission()
        content = UN.UNMutableNotificationContent.alloc.return_value.init.return_value
        threads = [item.args[0] for item in content.setThreadIdentifier_.call_args_list]
        self.assertEqual(threads, ["token-a", "token-b"])
        self.assertEqual(content.setSound_.call_args_list,
                         [call(UN.UNNotificationSound.defaultSound.return_value)] * 2)
        options = center.requestAuthorizationWithOptions_completionHandler_.call_args.args[0]
        self.assertTrue(options & UN.UNAuthorizationOptionSound)
        self.assertFalse(failures)


if __name__ == "__main__":
    unittest.main()
