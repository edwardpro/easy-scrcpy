import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QProcess
from easy_scrcpy.core import Device, Settings, device_input, scrcpy_arguments
from easy_scrcpy.app import Controller
from easy_scrcpy.monitor import DeviceMonitor
from easy_scrcpy.ui import InputDialog
from easy_scrcpy.i18n import set_language, tr
from test_qt import APP, wait_until


class KeyboardTests(unittest.TestCase):
    def tearDown(self):
        set_language("zh")
        APP.processEvents()

    def test_defaults_arguments_and_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            path.write_text('{}', encoding='utf-8')
            settings = Settings.load(path)
            self.assertEqual(device_input('a', settings), {'keyboard': 'sdk', 'clipboard_autosync': True})
            settings.device_input['a'] = {'keyboard': 'uhid', 'clipboard_autosync': False}
            settings.save(path)
            self.assertEqual(Settings.load(path), settings)
            for serial, keyboard in [('a', 'uhid'), ('b', 'sdk')]:
                args = scrcpy_arguments(Device(serial, 'device'), settings)
                self.assertIn('--serial=' + serial, args)
                self.assertIn('--keyboard=' + keyboard, args)
                self.assertEqual('--no-clipboard-autosync' in args, serial == 'a')
            for options in [None, [], {}, {'keyboard': 'aoa', 'clipboard_autosync': True},
                            {'keyboard': 'sdk', 'clipboard_autosync': 1}]:
                path.write_text(json.dumps({'device_input': {'a': options}}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    Settings.load(path)

    def test_controller_isolation_save_failure_and_disconnect(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(DeviceMonitor, 'start'), patch.object(DeviceMonitor, 'scan'), patch('easy_scrcpy.app.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
            controller = Controller(APP, Path(temp) / 'settings.json', Settings(prompt_on_connect=False), background=True)
            a, b = Device('a', 'device'), Device('b', 'device')
            options = {'keyboard': 'uhid', 'clipboard_autosync': False}
            try:
                controller.on_snapshot([a, b])
                controller.manager.processes = {'a': object(), 'b': object()}
                with patch.object(controller.manager, 'restart') as restart:
                    controller.save_input('a', options)
                    restart.assert_called_once_with(a)
                    self.assertEqual(device_input('b', controller.settings)['keyboard'], 'sdk')
                    controller.save_input('a', options)
                    restart.assert_called_once()
                    with patch.object(Settings, 'save', side_effect=OSError('denied')), patch.object(controller, 'show_error') as error:
                        controller.save_input('a', {'keyboard': 'sdk', 'clipboard_autosync': True})
                        error.assert_called_once()
                        self.assertEqual(device_input('a', controller.settings), options)
                controller.manager.processes = {}
                controller.open_input('a')
                dialog = controller.input_dialogs['a']
                for lang in ('en', 'fr', 'de', 'ja', 'zh'):
                    set_language(lang)
                    dialog.retranslate()
                    self.assertEqual(dialog.windowTitle(), tr('键盘输入'))
                    self.assertEqual(dialog.keyboard.itemText(1), tr('物理键盘（UHID，推荐）'))
                controller.on_snapshot([b])
                self.assertFalse(controller.input_dialogs)
                self.assertFalse(dialog.timer.isActive())
            finally:
                controller.manager.processes = {}
                controller.cleanup()
                controller.window.hide()
                controller.deleteLater()

    def test_physical_settings_arguments_failure_and_timeout_cleanup(self):
        dialog = InputDialog(Device('example', 'device'), Settings(), None)
        try:
            with patch('easy_scrcpy.ui.resolve_executable', return_value='/nonexistent/adb'):
                # FailedToStart may be delivered before start() returns on Windows.
                # Inspect arguments before starting, then exercise immediate cleanup.
                with patch.object(QProcess, 'start') as start, patch.object(
                        QProcess, 'readAllStandardOutput', return_value=b''):
                    dialog.open_physical_settings()
                    command = dialog.command
                    self.assertEqual(command.arguments(), ['-s', 'example', 'shell', 'am', 'start', '-a', 'android.settings.HARD_KEYBOARD_SETTINGS'])
                    start.assert_called_once_with()
                    command.errorOccurred.emit(QProcess.ProcessError.FailedToStart)
                self.assertIsNone(dialog.command)
                self.assertFalse(dialog.timer.isActive())
                self.assertTrue(dialog.physical.isEnabled())
                # Reproduce Windows: emit the failure inside start(), before it returns.
                def fail_immediately():
                    dialog.command.errorOccurred.emit(QProcess.ProcessError.FailedToStart)

                with patch.object(QProcess, 'start', side_effect=fail_immediately), patch.object(
                        QProcess, 'readAllStandardOutput', return_value=b''):
                    dialog.open_physical_settings()
                self.assertIsNone(dialog.command)
                self.assertFalse(dialog.timer.isActive())
                self.assertTrue(dialog.physical.isEnabled())
                # Do not access the process after starting: it may already be deleted.
                dialog.open_physical_settings()
                wait_until(lambda: dialog.command is None)
                self.assertIsNone(dialog.command)
                self.assertEqual(dialog.status.text(), tr('无法打开物理键盘设置'))
            command = QProcess(dialog)
            dialog.command = command
            command.finished.connect(dialog.command_finished)
            command.errorOccurred.connect(lambda _: None)
            dialog.timer.start(5000)
            dialog.timeout()
            self.assertIsNone(dialog.command)
            self.assertFalse(dialog.timer.isActive())
        finally:
            dialog.cleanup()
            dialog.deleteLater()
