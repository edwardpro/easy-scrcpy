from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from easy_scrcpy.app import Controller
from easy_scrcpy.core import Device, Settings, device_quality, scrcpy_arguments
from easy_scrcpy.i18n import set_language
from easy_scrcpy.mirroring import MirroringManager
from easy_scrcpy.monitor import DeviceMonitor
from test_qt import APP, wait_until


class QualityTests(unittest.TestCase):
    def tearDown(self):
        set_language("zh")
        APP.processEvents()

    def test_presets_custom_and_validation(self):
        device = Device("a", "device", usb=True)
        for profile, expected in (("smooth", (1024, 30, 2)), ("standard", (1920, 60, 8)), ("high", (0, 60, 16))):
            settings = Settings(device_quality={"a": {"profile": profile}})
            quality = device_quality("a", settings)
            self.assertEqual((quality["max_size"], quality["max_fps"], quality["video_bit_rate"]), expected)
            args = scrcpy_arguments(device, settings)
            self.assertIn(f"--video-bit-rate={expected[2]}M", args)
            self.assertIn(f"--max-fps={expected[1]}", args)
            self.assertEqual(any(arg.startswith("--max-size=") for arg in args), bool(expected[0]))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(device_quality={"a": {"profile": "custom", "max_size": 1280, "max_fps": 45, "video_bit_rate": 5}})
            settings.save(path)
            self.assertEqual(Settings.load(path), settings)
            for data in ({"profile": "bad"}, {"profile": "custom", "max_size": -1}, [], {"profile": "custom", "max_size": 1280, "max_fps": True, "video_bit_rate": 5}):
                path.write_text(json.dumps({"device_quality": {"a": data}}))
                with self.assertRaises(ValueError):
                    Settings.load(path)

    def test_panel_saves_selection_and_custom_cancel_restores_it(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(DeviceMonitor, "start"), patch.object(DeviceMonitor, "scan"), patch(
                "easy_scrcpy.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            controller = Controller(APP, Path(temp) / "settings.json", Settings(language="en", prompt_on_connect=False), background=True)
            try:
                controller.on_snapshot([Device("a", "device", usb=True)])
                controller.select_quality("a", "smooth")
                self.assertEqual(Settings.load(controller.config_path).device_quality["a"]["profile"], "smooth")
                combo = controller.window.table.cellWidget(0, 3).layout().itemAt(0).widget()
                controller.on_snapshot([Device("a", "device", usb=True)])
                self.assertIs(controller.window.table.cellWidget(0, 3).layout().itemAt(0).widget(), combo)
                combo.setCurrentIndex(combo.findData("custom"))
                controller.select_quality("a", "custom")
                controller.quality_dialogs["a"].reject()
                combo = controller.window.table.cellWidget(0, 3).layout().itemAt(0).widget()
                self.assertEqual(combo.currentData(), "smooth")
                controller.open_quality("a")
                dialog = controller.quality_dialogs["a"]
                dialog.size.setValue(1440)
                dialog.bitrate.setValue(10)
                dialog.accept()
                self.assertEqual(controller.settings.device_quality["a"]["max_size"], 1440)
            finally:
                controller.cleanup()
                controller.window.hide()
                controller.deleteLater()

    def test_restart_isolated_and_never_disables_debug(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "helper.py"
            script.write_text("import time\nprint('ready', flush=True)\ntime.sleep(60)\n")
            manager = MirroringManager(Settings(disable_debug_on_stop=True))
            logs = []
            manager.log.connect(logs.append)
            manager.restart_ready.connect(manager.start)
            a, b = Device("a", "device", usb=True), Device("b", "device", usb=True)
            try:
                with patch("easy_scrcpy.mirroring.resolve_executable", return_value=sys.executable), patch(
                        "easy_scrcpy.mirroring.scrcpy_arguments", return_value=[str(script)]):
                    manager.start(a)
                    manager.start(b)
                    wait_until(lambda: len(logs) == 2)
                    old_a = manager.processes["a"]
                    old_b = manager.processes["b"]
                    manager.restart(a)
                    wait_until(lambda: "a" in manager.processes and manager.processes["a"] is not old_a)
                    self.assertIs(manager.processes["b"], old_b)
                    self.assertFalse(manager.debug_commands)
                    wait_until(lambda: len(logs) == 3)
                    manager.restart(a)
                    manager.stop("a")  # unplug cancels pending restart
                    wait_until(lambda: "a" not in manager.processes)
                    self.assertFalse(manager.restarts)
            finally:
                manager.shutdown()
