from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QToolButton

from easy_scrcpy.app import app_icon, tray_icon, icon_path
from easy_scrcpy.core import Device, Settings
from easy_scrcpy.ui import ControlWindow
from easy_scrcpy.i18n import set_language
from test_qt import APP


class IconTests(unittest.TestCase):
    def test_stop_button_icon_preserves_action_and_translations(self):
        window = ControlWindow(app_icon())
        manager = SimpleNamespace(processes={"a": object()}, stopping=set(), settings=Settings())
        stopped = []
        window.stop_requested.connect(stopped.append)
        try:
            for language, label in (("en", "Stop mirroring"), ("zh", "停止投屏")):
                set_language(language)
                window.retranslate()
                window.update_devices([Device("a", "device", usb=True)], manager)
                button = window.table.cellWidget(0, 4).findChild(QToolButton)
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.text(), "")
                self.assertEqual(button.toolTip(), label)
                self.assertEqual(button.accessibleName(), label)
                self.assertEqual(button.width(), 40)
                self.assertEqual(button.height(), 40)
                self.assertEqual(button.iconSize().width(), 24)
                self.assertGreaterEqual(window.table.rowHeight(0), 56)
                button.click()
            self.assertEqual(stopped, ["a", "a"])
            manager.stopping.add("a")
            window.update_devices([Device("a", "device", usb=True)], manager)
            self.assertFalse(window.table.cellWidget(0, 4).findChild(QToolButton).isEnabled())
            manager.processes.clear()
            manager.stopping.clear()
            window.update_devices([Device("a", "device", usb=True)], manager)
            start_button = window.table.cellWidget(0, 4).findChild(QToolButton)
            self.assertFalse(start_button.icon().isNull())
            self.assertEqual(start_button.accessibleName(), "开始投屏")
            self.assertEqual(start_button.size(), button.size())
            requested = []
            window.custom_quality_requested.connect(requested.append)
            config_button = window.table.cellWidget(0, 3).findChild(QToolButton, "qualityConfigButton")
            self.assertFalse(config_button.icon().isNull())
            self.assertEqual(config_button.text(), "")
            self.assertEqual(config_button.size(), start_button.size())
            self.assertEqual(config_button.iconSize(), start_button.iconSize())
            self.assertEqual(config_button.toolTip(), "调整…")
            self.assertEqual(config_button.accessibleName(), "自定义画质")
            config_button.click()
            self.assertEqual(requested, ["a"])
        finally:
            set_language("zh")
            window.deleteLater()

    def test_mac_template_uses_monochrome_artwork_and_alpha(self):
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / "assets"
            assets.mkdir()
            image = QImage(64, 64, QImage.Format.Format_ARGB32)
            image.fill(QColor("white"))
            image.setPixelColor(32, 32, QColor("black"))
            image.save(str(assets / "tray-icon-mac.png"))
            with patch.object(sys, "platform", "darwin"), patch.object(sys, "frozen", True, create=True), patch.object(
                    sys, "_MEIPASS", temp, create=True):
                icon = tray_icon()
                self.assertTrue(icon.isMask())
                result = icon.pixmap(64, 64).toImage()
                self.assertEqual(result.pixelColor(0, 0).alpha(), 0)
                self.assertEqual(result.pixelColor(32, 32).alpha(), 255)

    def test_separate_app_and_tray_images_in_frozen_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / "assets"
            assets.mkdir()
            for name, size, color in (("icon.png", 1024, "red"), ("tray-icon.png", 64, "blue")):
                image = QImage(size, size, QImage.Format.Format_ARGB32)
                image.fill(QColor(color))
                self.assertTrue(image.save(str(assets / name)))
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", temp, create=True):
                self.assertEqual(icon_path("icon.png"), assets / "icon.png")
                self.assertEqual(app_icon().pixmap(32, 32).toImage().pixelColor(16, 16), QColor("red"))
                self.assertEqual(tray_icon().pixmap(32, 32).toImage().pixelColor(16, 16), QColor("blue"))

    def test_missing_images_fall_back(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "_MEIPASS", temp, create=True):
            self.assertFalse(app_icon().isNull())
            self.assertFalse(tray_icon().isNull())
