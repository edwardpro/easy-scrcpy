import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from easy_scrcpy.app import Controller
from easy_scrcpy.core import Device, Settings, ORIENTATION_OPTIONS, scrcpy_arguments
from easy_scrcpy.i18n import set_language, tr
from easy_scrcpy.monitor import DeviceMonitor
from easy_scrcpy.ui import orientation_combo
from test_qt import APP


class OrientationTests(unittest.TestCase):
    def tearDown(self):
        set_language("zh")
        APP.processEvents()

    def test_arguments_per_device_and_default_omitted(self):
        settings = Settings(device_orientation={"a": 90, "b": 0})
        self.assertIn("--capture-orientation=@90", scrcpy_arguments(Device("a", "device", usb=True), settings))
        for serial in ("b", "c"):
            args = scrcpy_arguments(Device(serial, "device", usb=True), settings)
            self.assertFalse(any(arg.startswith("--capture-orientation") for arg in args))

    def test_settings_roundtrip_validation_and_backward_compatibility(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(device_orientation={"a": 270, "b": 0})
            settings.save(path)
            self.assertEqual(Settings.load(path), settings)
            self.assertFalse(path.with_suffix(".tmp").exists())
            path.write_text('{"audio": false}')
            self.assertEqual(Settings.load(path).device_orientation, {})
            for data in ({"device_orientation": {"a": 45}}, {"device_orientation": {"a": "90"}},
                         {"device_orientation": {"a": True}}, {"device_orientation": []}):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    Settings.load(path)

    def test_combo_options_non_editable_and_labels(self):
        combo = orientation_combo(0)
        try:
            self.assertFalse(combo.isEditable())
            self.assertEqual(combo.currentData(), 0)
            self.assertEqual(combo.itemText(combo.findData(0)), "默认")
            self.assertEqual(combo.itemText(combo.findData(90)), "90°")
            self.assertTrue(all(combo.findData(value) != -1 for value in ORIENTATION_OPTIONS))
        finally:
            combo.deleteLater()
        set_language("en")
        combo = orientation_combo(0)
        try:
            self.assertEqual(combo.itemText(combo.findData(0)), "Default")
        finally:
            combo.deleteLater()

    def test_panel_selection_saves_and_restarts_running_device(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(DeviceMonitor, "start"), patch.object(
                DeviceMonitor, "scan"), patch("easy_scrcpy.app.QSystemTrayIcon.isSystemTrayAvailable",
                                              return_value=False):
            controller = Controller(APP, Path(temp) / "settings.json",
                                    Settings(language="zh", prompt_on_connect=False), background=True)
            try:
                controller.on_snapshot([Device("a", "device", usb=True)])
                self.assertEqual(controller.window.table.horizontalHeaderItem(4).text(), "方向")
                controller.select_orientation("a", 90)
                self.assertEqual(Settings.load(controller.config_path).device_orientation, {"a": 90})
                combo = controller.window.table.cellWidget(0, 4)
                self.assertEqual(combo.currentData(), 90)
                controller.select_orientation("a", 45)
                self.assertEqual(Settings.load(controller.config_path).device_orientation, {"a": 90})
                with patch.object(controller.manager, "restart") as restart:
                    controller.manager.processes = {"a": object()}
                    try:
                        controller.select_orientation("a", 180)
                        restart.assert_called_once()
                    finally:
                        controller.manager.processes = {}
                settings = replace(Settings.load(controller.config_path), language="en")
                controller.apply_settings(settings)
                combo = controller.window.table.cellWidget(0, 4)
                self.assertEqual(combo.currentData(), 180)
                self.assertEqual(combo.itemText(combo.findData(0)), tr("默认"))
                self.assertEqual(combo.toolTip(),
                                 tr("锁定捕获方向，手机物理旋转不会带动投屏画面；修改会重启该设备投屏。"))
            finally:
                controller.cleanup()
                controller.window.hide()
                controller.deleteLater()
