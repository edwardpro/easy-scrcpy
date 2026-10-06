from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QProcess

from easy_scrcpy.core import Device, Settings
from easy_scrcpy.i18n import set_language
from easy_scrcpy.mirroring import MirroringManager
from test_qt import APP, wait_until


class DebugStopTests(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = MirroringManager(Settings(disable_debug_on_stop=True))
        self.errors, self.logs = [], []
        self.manager.error.connect(self.errors.append)
        self.manager.log.connect(self.logs.append)
        script = self.root / "mirror.py"
        script.write_text("import time\nprint('ready', flush=True)\ntime.sleep(60)\n")
        with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch(
                "easy_scrcpy.mirroring.scrcpy_arguments", return_value=[str(script)]):
            self.manager.start(Device("a", "device", usb=True))
            self.manager.start(Device("b", "device", usb=True))
        wait_until(lambda: len(self.logs) >= 2)

    def tearDown(self):
        self.manager.shutdown()
        APP.processEvents()
        self.temp.cleanup()
        set_language("zh")

    def request(self, body):
        script = self.root / "adb.py"
        script.write_text(body)
        original = QProcess.setArguments
        arguments = []
        def redirect(process, args):
            arguments.append(args)
            original(process, [str(script)])
        with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch.object(
                QProcess, "setArguments", redirect):
            self.manager.request_stop("a")
            self.manager.request_stop("a")
        self.assertEqual(arguments, [["-s", "a", "shell", "settings", "put", "global", "adb_enabled", "0"]])

    def test_success_before_mirror_stop_and_other_device_unaffected(self):
        self.request("import time\ntime.sleep(0.15)\n")
        self.assertIn("a", self.manager.processes)
        self.assertNotIn("a", self.manager.terminating)
        wait_until(lambda: "a" not in self.manager.processes)
        self.assertIn("b", self.manager.processes)
        self.assertFalse(self.errors)
        self.assertTrue(any("request sent" in line for line in self.logs))

    def test_permission_denied_still_stops(self):
        self.request("import sys\nprint('SecurityException: permission denied')\nsys.exit(1)\n")
        wait_until(lambda: "a" not in self.manager.processes)
        self.assertTrue(any("permission denied" in text for text in self.errors))
        self.assertIn("b", self.manager.processes)

    def test_timeout_still_stops(self):
        self.request("import time\ntime.sleep(60)\n")
        wait_until(lambda: "a" not in self.manager.processes, timeout=6)
        self.assertTrue(any("timed out" in text for text in self.errors))
        self.assertFalse(self.manager.debug_commands)

    def test_disabled_option_and_automatic_stop_never_run_adb(self):
        self.manager.settings.disable_debug_on_stop = False
        with patch("easy_scrcpy.mirroring.resolve_executable") as resolve:
            self.manager.request_stop("a")
            self.manager.settings.disable_debug_on_stop = True
            self.manager.stop("b")
            resolve.assert_not_called()
        wait_until(lambda: not self.manager.processes)

    def test_missing_adb_still_stops(self):
        with patch("easy_scrcpy.mirroring.resolve_executable", return_value=None):
            self.manager.request_stop("a")
        wait_until(lambda: "a" not in self.manager.processes)
        self.assertTrue(any("ADB not found" in text for text in self.errors))

    def test_unplug_during_request_and_shutdown(self):
        self.request("import time\ntime.sleep(60)\n")
        self.manager.stop("a")
        wait_until(lambda: "a" not in self.manager.processes)
        self.assertIn("a", self.manager.stopping)
        self.manager.shutdown()
        self.assertFalse(self.manager.debug_commands)
        self.assertFalse(self.manager.processes)
        self.assertFalse(self.manager.stopping)

    def test_failed_to_start_still_stops(self):
        with patch("easy_scrcpy.mirroring.resolve_executable", return_value=str(self.root / "missing")):
            self.manager.request_stop("a")
        wait_until(lambda: "a" not in self.manager.processes)
        self.assertTrue(self.errors)
