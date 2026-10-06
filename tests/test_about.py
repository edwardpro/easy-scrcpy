import unittest
from string import Formatter

from PySide6.QtWidgets import QLabel, QPushButton, QDialog

from easy_scrcpy import __version__
from easy_scrcpy.i18n import CATALOG, ROWS, set_language, tr
from easy_scrcpy.ui import AboutDialog
from test_qt import APP


class AboutTests(unittest.TestCase):
    def test_about_content_and_close_in_all_languages(self):
        try:
            for language in ("zh", "en", "fr", "de", "ja"):
                set_language(language)
                dialog = AboutDialog()
                self.assertEqual(dialog.windowTitle(), tr("关于"))
                labels = [label.text() for label in dialog.findChildren(QLabel)]
                self.assertIn(tr("版本：{version}", version=__version__), labels)
                repository = next(label for label in dialog.findChildren(QLabel) if "https://github.com/edwardpro/easy-scrcpy" in label.text())
                self.assertTrue(repository.openExternalLinks())
                close = dialog.findChild(QPushButton)
                self.assertEqual(close.text(), tr("关闭"))
                dialog.show()
                close.click()
                self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
                self.assertFalse(dialog.isVisible())
                APP.processEvents()
        finally:
            set_language("zh")

    def test_translation_catalog_and_placeholders(self):
        self.assertEqual(len(ROWS), len(CATALOG["zh"]))
        def fields(text):
            return {field for _, field, _, _ in Formatter().parse(text) if field is not None}
        for catalog in CATALOG.values():
            self.assertEqual(set(catalog), set(CATALOG["zh"]))
            for source, translated in catalog.items():
                self.assertEqual(fields(source), fields(translated))
