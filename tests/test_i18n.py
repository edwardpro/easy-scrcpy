from dataclasses import replace
from pathlib import Path
from string import Formatter
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QLabel, QMessageBox

from easy_scrcpy.app import Controller
from easy_scrcpy.core import Device, Settings
from easy_scrcpy.i18n import CATALOG, LANGUAGES, ROWS, language_for_locale, set_language, tr
from easy_scrcpy.monitor import DeviceMonitor
from test_qt import APP


class TranslationTests(unittest.TestCase):
    def tearDown(self):
        set_language("zh")
        APP.processEvents()

    def test_complete_catalog_and_placeholders(self):
        self.assertEqual(len(ROWS), len(CATALOG["zh"]))
        formatter = Formatter()
        def placeholders(text):
            return {name for _, name, _, _ in formatter.parse(text) if name is not None}
        for language, catalog in CATALOG.items():
            self.assertEqual(set(catalog), set(CATALOG["zh"]))
            for source, translated in catalog.items():
                self.assertTrue(translated, (language, source))
                self.assertEqual(placeholders(source), placeholders(translated), (language, source))

    def test_locale_and_fallback(self):
        for locale, language in (("zh-TW", "zh"), ("en_US", "en"), ("fr-FR", "fr"),
                                 ("de_DE", "de"), ("ja_JP", "ja"), ("es_ES", "en")):
            self.assertEqual(language_for_locale(locale), language)
        set_language("en")
        self.assertEqual(tr("设置"), "Settings")
        self.assertEqual(tr("raw process output {not_a_placeholder}"), "raw process output {not_a_placeholder}")
        self.assertEqual(tr("{device}\n\n是否开始投屏？", device="Pixel"), "Pixel\n\nStart mirroring?")

    def test_settings_backward_compatibility_and_language_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            path.write_text('{"audio": false}')
            self.assertEqual(Settings.load(path).language, "auto")
            for language in LANGUAGES:
                settings = Settings(language=language)
                settings.save(path)
                self.assertEqual(Settings.load(path), settings)
            path.write_text('{"language": "invalid"}')
            with self.assertRaises(ValueError):
                Settings.load(path)

    def test_live_language_switch_preserves_devices_logs_and_prompts(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(DeviceMonitor, "start"), patch.object(
                DeviceMonitor, "scan"), patch("easy_scrcpy.app.QSystemTrayIcon.isSystemTrayAvailable", return_value=False):
            controller = Controller(APP, Path(temp) / "settings.json", Settings(language="zh"), background=True)
            try:
                device = Device("a", "device", "Pixel", True)
                controller.on_snapshot([device])
                dialog = controller.prompts["a"]
                controller.on_health("正在监听 USB Android 设备")
                controller.log("unchanged raw output {test}")
                for language in ("en", "fr", "de", "ja", "zh", "en"):
                    controller.apply_settings(replace(controller.settings, language=language))
                    self.assertEqual(controller.menu.actions()[0].text(), tr("打开设备面板"))
                    self.assertEqual(controller.window.table.horizontalHeaderItem(0).text(), tr("设备"))
                    self.assertEqual(controller.window.table.item(0, 2).text(), tr("已就绪"))
                    self.assertEqual(controller.window.health.text(), tr("正在监听 USB Android 设备"))
                    self.assertEqual(dialog.button(QMessageBox.StandardButton.Yes).text(), tr("是"))
                    self.assertEqual(dialog.text(), tr("{device}\n\n是否开始投屏？", device=device.label))
                    self.assertTrue(any(label.text() == tr("Easy Scrcpy · USB 设备投屏")
                                        for label in controller.window.findChildren(QLabel)))
                self.assertIn("unchanged raw output {test}", controller.window.logs.toPlainText())
                self.assertIs(controller.prompts["a"], dialog)
                controller.open_settings()
                settings_dialog = controller.settings_dialog
                self.assertEqual(settings_dialog.windowTitle(), "Settings")
                self.assertEqual(settings_dialog.language.currentData(), "en")
                settings_dialog.language.setCurrentIndex(settings_dialog.language.findData("fr"))
                settings_dialog.save()
                self.assertEqual(Settings.load(controller.config_path).language, "fr")
                self.assertEqual(controller.menu.actions()[0].text(), "Ouvrir le panneau des appareils")
                dialog.reject()
            finally:
                controller.cleanup()
                controller.window.hide()
                controller.deleteLater()
