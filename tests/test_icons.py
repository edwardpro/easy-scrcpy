from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QToolButton, QComboBox, QGraphicsDropShadowEffect, QHeaderView

from easy_scrcpy.app import app_icon, tray_icon, icon_path
from easy_scrcpy.core import Device, Settings
from easy_scrcpy.ui import ControlWindow
from easy_scrcpy.i18n import LANGUAGES, set_language, tr
from test_qt import APP


class IconTests(unittest.TestCase):
    def test_device_row_controls_align_without_clipping(self):
        window = ControlWindow(app_icon())
        manager = SimpleNamespace(processes={}, stopping=set(), settings=Settings())
        try:
            window.update_devices([Device("demo", "device")], manager)
            window.show()
            APP.processEvents()
            self.assertEqual(window.table.horizontalHeader().sectionResizeMode(2),
                             QHeaderView.ResizeMode.ResizeToContents)
            controls = []
            for column in (3, 4, 5):
                cell = window.table.cellWidget(0, column)
                controls.extend(cell.findChildren(QToolButton))
                controls.extend(cell.findChildren(QComboBox))
            centers = []
            for control in controls:
                self.assertEqual(control.height(), 35)
                centers.append(control.mapTo(window.table.viewport(), control.rect().center()).y())
                if isinstance(control, QToolButton):
                    self.assertIsInstance(control.graphicsEffect(), QGraphicsDropShadowEffect)
                    self.assertGreater(control.graphicsEffect().blurRadius(), 0)
            self.assertLessEqual(max(centers) - min(centers), 1)
            self.assertGreaterEqual(window.table.rowHeight(0), 56)
        finally:
            window.hide()
            window.deleteLater()

    def test_keyboard_icon_preserves_target_translations_and_enabled_state(self):
        window = ControlWindow(app_icon())
        manager = SimpleNamespace(processes={}, stopping=set(), settings=Settings())
        devices = [Device("usb", "device", usb=True), Device("wifi", "device"), Device("offline", "offline")]
        requested = []
        window.input_requested.connect(requested.append)
        try:
            for language in LANGUAGES:
                set_language(language)
                window.retranslate()
                window.update_devices(devices, manager)
                for row, device in enumerate(devices):
                    cell = window.table.cellWidget(row, 5)
                    button = cell.findChild(QToolButton, "keyboardSettingsButton")
                    self.assertIs(cell.layout().itemAt(cell.layout().count() - 1).widget(), button)
                    self.assertFalse(button.icon().isNull())
                    self.assertEqual(button.text(), "")
                    self.assertEqual(button.toolTip(), tr("键盘输入…"))
                    self.assertEqual(button.accessibleName(), tr("键盘输入…"))
                    self.assertEqual((button.width(), button.height()), (35, 35))
                    self.assertEqual((button.iconSize().width(), button.iconSize().height()), (21, 21))
                    self.assertEqual(button.isEnabled(), device.state == "device")
                    button.click()
            self.assertEqual(requested, ["usb", "wifi"] * len(LANGUAGES))
            manager.stopping.add("wifi")
            window.update_devices(devices, manager)
            self.assertFalse(window.table.cellWidget(1, 5).findChild(QToolButton, "keyboardSettingsButton").isEnabled())
            self.assertTrue(window.table.cellWidget(0, 5).findChild(QToolButton, "keyboardSettingsButton").isEnabled())
        finally:
            set_language("zh")
            window.deleteLater()

    def test_wireless_disconnect_button_order_target_and_translations(self):
        window = ControlWindow(app_icon())
        manager = SimpleNamespace(processes={"wifi-a": object()}, stopping=set(), settings=Settings())
        devices = [Device("usb", "device", usb=True), Device("wifi-a", "device"),
                   Device("wifi-b", "offline")]
        requested = []
        window.disconnect_wireless_requested.connect(requested.append)
        try:
            for language in LANGUAGES:
                set_language(language)
                window.retranslate()
                window.update_devices(devices, manager)
                self.assertIsNone(window.table.cellWidget(0, 5).findChild(QToolButton, "disconnectWirelessButton"))
                for row, serial in ((1, "wifi-a"), (2, "wifi-b")):
                    cell = window.table.cellWidget(row, 5)
                    button = cell.findChild(QToolButton, "disconnectWirelessButton")
                    self.assertIs(cell.layout().itemAt(0).widget(), button)
                    self.assertEqual(cell.layout().itemAt(1).widget().objectName(), "mirrorActionButton")
                    self.assertFalse(button.icon().isNull())
                    self.assertEqual(button.text(), "")
                    self.assertEqual(button.toolTip(), tr("断开无线连接"))
                    self.assertEqual(button.accessibleName(), tr("断开无线连接"))
                    self.assertEqual((button.width(), button.height()), (35, 35))
                    self.assertEqual((button.iconSize().width(), button.iconSize().height()), (21, 21))
                    self.assertGreaterEqual(window.table.rowHeight(row), 56)
                    button.click()
                    self.assertEqual(requested[-1], serial)
            self.assertEqual(requested, ["wifi-a", "wifi-b"] * len(LANGUAGES))
            manager.stopping.add("wifi-a")
            window.update_devices(devices, manager)
            self.assertFalse(window.table.cellWidget(1, 5).findChild(QToolButton, "disconnectWirelessButton").isEnabled())
            self.assertTrue(window.table.cellWidget(2, 5).findChild(QToolButton, "disconnectWirelessButton").isEnabled())
        finally:
            set_language("zh")
            window.deleteLater()

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
                button = window.table.cellWidget(0, 5).findChild(QToolButton)
                self.assertFalse(button.icon().isNull())
                self.assertEqual(button.text(), "")
                self.assertEqual(button.toolTip(), label)
                self.assertEqual(button.accessibleName(), label)
                self.assertEqual(button.width(), 35)
                self.assertEqual(button.height(), 35)
                self.assertEqual(button.iconSize().width(), 21)
                self.assertGreaterEqual(window.table.rowHeight(0), 56)
                button.click()
            self.assertEqual(stopped, ["a", "a"])
            manager.stopping.add("a")
            window.update_devices([Device("a", "device", usb=True)], manager)
            self.assertFalse(window.table.cellWidget(0, 5).findChild(QToolButton).isEnabled())
            manager.processes.clear()
            manager.stopping.clear()
            window.update_devices([Device("a", "device", usb=True)], manager)
            start_button = window.table.cellWidget(0, 5).findChild(QToolButton)
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
