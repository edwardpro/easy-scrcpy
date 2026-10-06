from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtGui import QImage, QColor

from easy_scrcpy.app import app_icon, tray_icon, icon_path
from test_qt import APP


class IconTests(unittest.TestCase):
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
