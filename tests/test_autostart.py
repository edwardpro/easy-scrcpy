from pathlib import Path
import plistlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from easy_scrcpy.autostart import Autostart, desktop_exec


class AutostartTests(unittest.TestCase):
    def test_macos_registration_and_removal(self):
        with tempfile.TemporaryDirectory() as temp:
            manager = Autostart("darwin", Path(temp))
            command = ["/Applications/My App.app/Contents/MacOS/app", "--background"]
            with patch("easy_scrcpy.autostart.launch_command", return_value=command):
                manager.set_enabled(True)
            self.assertTrue(manager.enabled())
            self.assertEqual(plistlib.loads(manager.path.read_bytes())["ProgramArguments"], command)
            manager.set_enabled(False)
            manager.set_enabled(False)
            self.assertFalse(manager.enabled())

    def test_linux_registration(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": temp}):
                manager = Autostart("linux", Path(temp))
                with patch("easy_scrcpy.autostart.launch_command", return_value=["/my app/python", "-m", "easy_scrcpy", "--background"]):
                    manager.set_enabled(True)
                self.assertIn('Exec="/my app/python" "-m" "easy_scrcpy" "--background"', manager.path.read_text())
                manager.set_enabled(False)
                self.assertFalse(manager.enabled())

    def test_desktop_exec_escaping(self):
        self.assertEqual(desktop_exec(["/path/100%/$app"]), '"/path/100%%/\\$app"')

    def test_windows_registration(self):
        values = {}

        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def query(key, name):
            if name not in values:
                raise FileNotFoundError(name)
            return values[name], 1

        def delete(key, name):
            if name not in values:
                raise FileNotFoundError(name)
            del values[name]

        winreg = SimpleNamespace(HKEY_CURRENT_USER=1, REG_SZ=1,
                                 OpenKey=lambda *args: Key(), CreateKey=lambda *args: Key(),
                                 QueryValueEx=query, DeleteValue=delete,
                                 SetValueEx=lambda key, name, reserved, kind, value: values.update({name: value}))
        with patch.dict("sys.modules", {"winreg": winreg}), patch(
                "easy_scrcpy.autostart.launch_command", return_value=[r"C:\Program Files\EasyScrcpy.exe", "--background"]):
            manager = Autostart("win32")
            self.assertFalse(manager.enabled())
            manager.set_enabled(True)
            self.assertTrue(manager.enabled())
            self.assertEqual(values["EasyScrcpy"], '"C:\\Program Files\\EasyScrcpy.exe" --background')
            manager.set_enabled(False)
            manager.set_enabled(False)
            self.assertFalse(manager.enabled())
