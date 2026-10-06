import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication, QMessageBox

from easy_scrcpy.app import Controller
from easy_scrcpy.core import Device, Settings
from easy_scrcpy.mirroring import MirroringManager
from easy_scrcpy.monitor import DeviceMonitor
from easy_scrcpy.i18n import set_language

APP = QApplication.instance() or QApplication(["test-easy-scrcpy"])
APP.setQuitOnLastWindowClosed(False)


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        APP.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Qt operation timed out")


class QtTests(unittest.TestCase):
    def setUp(self):
        set_language("zh")
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

    def tearDown(self):
        APP.processEvents()
        self.temp.cleanup()

    def make_script(self, text):
        script = self.path / "helper.py"
        script.write_text(text, encoding="utf-8")
        return script

    def test_two_mirrors_stop_independently(self):
        script = self.make_script("import time\nprint('started', flush=True)\ntime.sleep(60)\n")
        manager = MirroringManager(Settings())
        errors, logs = [], []
        manager.error.connect(errors.append)
        manager.log.connect(logs.append)
        try:
            with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch(
                    "easy_scrcpy.mirroring.scrcpy_arguments", return_value=[str(script)]):
                manager.start(Device("a", "device", usb=True))
                manager.start(Device("b", "device", usb=True))
                manager.start(Device("a", "device", usb=True))
            wait_until(lambda: len(logs) == 2)
            self.assertEqual(len(manager.processes), 2)
            manager.stop("a")
            wait_until(lambda: "a" not in manager.processes)
            self.assertIn("b", manager.processes)
            self.assertEqual(manager.processes["b"].state(), QProcess.ProcessState.Running)
            self.assertEqual(errors, [])
        finally:
            manager.shutdown()
        self.assertEqual(manager.processes, {})

    def test_private_adb_and_server_environment(self):
        script = self.make_script("import time\ntime.sleep(60)\n")
        server = Path(sys.executable).parent / "scrcpy-server"
        manager = MirroringManager(Settings())
        try:
            original_is_file = Path.is_file
            with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch(
                    "easy_scrcpy.mirroring.scrcpy_arguments", return_value=[str(script)]), patch.object(
                    Path, "is_file", lambda p: True if p == server else original_is_file(p)):
                manager.start(Device("a", "device", usb=True))
            process = manager.processes["a"]
            self.assertEqual(process.processEnvironment().value("ADB"), sys.executable)
            self.assertEqual(process.processEnvironment().value("SCRCPY_SERVER_PATH"), str(server))
            wait_until(lambda: process.state() == QProcess.ProcessState.Running)
        finally:
            manager.shutdown()

    @unittest.skipIf(sys.platform == "win32", "POSIX SIGTERM behavior")
    def test_unresponsive_process_is_killed(self):
        script = self.make_script("import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nprint('ready', flush=True)\ntime.sleep(60)\n")
        manager = MirroringManager(Settings())
        logs = []
        manager.log.connect(logs.append)
        try:
            with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch(
                    "easy_scrcpy.mirroring.scrcpy_arguments", return_value=[str(script)]):
                manager.start(Device("a", "device", usb=True))
            wait_until(lambda: bool(logs))
            manager.stop("a")
            wait_until(lambda: not manager.processes, timeout=4)
        finally:
            manager.shutdown()

    def test_abnormal_exit_reports_output(self):
        script = self.make_script("import sys\nprint('simulated encoder failure', flush=True)\nsys.exit(7)\n")
        manager = MirroringManager(Settings())
        errors = []
        manager.error.connect(errors.append)
        with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch(
                "easy_scrcpy.mirroring.scrcpy_arguments", return_value=[str(script)]):
            manager.start(Device("a", "device", usb=True))
        wait_until(lambda: bool(errors))
        self.assertIn("simulated encoder failure", errors[0])
        self.assertIn("7", errors[0])
        self.assertFalse(manager.processes)

    def test_failed_to_start_cleanup(self):
        manager = MirroringManager(Settings())
        errors = []
        manager.error.connect(errors.append)
        with patch("easy_scrcpy.mirroring.resolve_executable", return_value=str(self.path / "does-not-exist")):
            manager.start(Device("a", "device", usb=True))
        wait_until(lambda: bool(errors))
        self.assertFalse(manager.processes)

    def test_monitor_usb_fallback_and_failed_scan(self):
        script = self.make_script("""import sys
from pathlib import Path
if Path(__file__).with_suffix('.fail').exists():
    print('simulated adb error', file=sys.stderr)
    sys.exit(1)
if sys.argv[1] == 'devices':
    print('List of devices attached')
    print('a device usb:1-1 model:Pixel_8')
    print('b device model:Pixel_9')
    print('c unauthorized usb:1-3')
    print('192.168.1.2:5555 device model:Wireless')
    print('emulator-5554 device')
else:
    print('usb:1-2')
""")

        class TestMonitor(DeviceMonitor):
            def _run(self, arguments):
                super()._run([str(script), *arguments])

        monitor = TestMonitor(Settings())
        snapshots, health = [], []
        monitor.snapshot.connect(snapshots.append)
        monitor.health.connect(health.append)
        try:
            with patch("easy_scrcpy.monitor.resolve_executable", return_value=sys.executable):
                monitor.scan()
                wait_until(lambda: len(snapshots) == 1)
                self.assertEqual([d.serial for d in snapshots[0]], ["a", "b", "c"])
                self.assertTrue(all(d.usb for d in snapshots[0]))
                script.with_suffix(".fail").touch()
                monitor.scan()
                wait_until(lambda: not monitor.active)
            self.assertEqual(len(snapshots), 1)
            self.assertIn("查询失败", health[-1])
        finally:
            monitor.stop()

    def test_monitor_timeout_does_not_emit_disconnect(self):
        script = self.make_script("import time\ntime.sleep(60)\n")

        class TestMonitor(DeviceMonitor):
            def _run(self, arguments):
                super()._run([str(script)])
                self.deadline.start(100)

        monitor = TestMonitor(Settings())
        snapshots, health = [], []
        monitor.snapshot.connect(snapshots.append)
        monitor.health.connect(health.append)
        try:
            with patch("easy_scrcpy.monitor.resolve_executable", return_value=sys.executable):
                monitor.scan()
                wait_until(lambda: not monitor.active)
            self.assertEqual(snapshots, [])
            self.assertTrue(any("超时" in text for text in health))
        finally:
            monitor.stop()

    def test_controller_prompts_and_unplug_routing(self):
        with patch.object(DeviceMonitor, "start"), patch("easy_scrcpy.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            controller = Controller(APP, self.path / "settings.json", Settings(language="zh"), background=True)
        a = Device("a", "device", "Pixel", True)
        b = Device("b", "device", "Pixel", True)
        try:
            controller.on_snapshot([a, b])
            self.assertEqual(set(controller.prompts), {"a", "b"})
            with patch.object(controller.manager, "start") as start:
                controller.prompts["a"].done(QMessageBox.StandardButton.Yes)
                start.assert_called_once_with(a)
            controller.prompts["b"].done(QMessageBox.StandardButton.No)
            controller.on_snapshot([a, b])
            self.assertFalse(controller.prompts)
            with patch.object(controller.manager, "stop") as stop:
                controller.on_snapshot([b])
                stop.assert_called_once_with("a")
            controller.on_snapshot([a, b])
            self.assertEqual(set(controller.prompts), {"a"})
            controller.on_snapshot([b])
            self.assertFalse(controller.prompts)
            controller.open_settings()
            self.assertIsNotNone(controller.settings_dialog)
            controller.settings_dialog.reject()
            self.assertIsNone(controller.settings_dialog)
        finally:
            controller.cleanup()
            controller.window.hide()
            controller.deleteLater()
