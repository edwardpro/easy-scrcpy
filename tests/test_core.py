import json
from pathlib import Path
import tempfile
import unittest

from easy_scrcpy.core import Device, Presence, Settings, parse_devices, resolve_executable, scrcpy_arguments


class CoreTests(unittest.TestCase):
    def test_parse_states_and_transports(self):
        output = """* daemon started successfully *
List of devices attached
USB1 device usb:1-2 product:foo model:Pixel_8 device:foo transport_id:1
USB2 unauthorized usb:1-3 transport_id:2
USB3 offline usb:1-4
USB4 no permissions (user in plugdev group); usb:1-5
192.168.1.2:5555 device model:Wireless transport_id:5
emulator-5554 device model:Emulator
"""
        devices = parse_devices(output)
        self.assertEqual(len(devices), 6)
        self.assertEqual(devices[0].label, "Pixel 8 (USB1)")
        self.assertEqual(devices[3].state, "no permissions")
        self.assertFalse(devices[4].usb)

    def test_prompt_once_authorize_disconnect_reconnect(self):
        presence = Presence()
        unauthorized = Device("a", "unauthorized", usb=True)
        ready = Device("a", "device", usb=True)
        self.assertEqual(presence.update([unauthorized]), ([], set()))
        self.assertEqual(presence.update([ready]), ([ready], set()))
        self.assertEqual(presence.update([ready]), ([], set()))
        self.assertEqual(presence.update([unauthorized]), ([], {"a"}))
        self.assertEqual(presence.update([ready]), ([], set()))
        self.assertEqual(presence.update([]), ([], {"a"}))
        self.assertEqual(presence.update([ready]), ([ready], set()))

    def test_multiple_devices_independent(self):
        presence = Presence()
        a = Device("a", "device", usb=True)
        b = Device("b", "device", usb=True)
        network = Device("host:5555", "device")
        self.assertEqual(presence.update([a, b, network]), ([a, b], set()))
        self.assertEqual(presence.update([b]), ([], {"a"}))
        self.assertEqual(presence.devices, {"b": b})

    def test_arguments_are_not_shell_commands(self):
        device = Device("a;echo bad", "device", "Pixel 8", True)
        args = scrcpy_arguments(device, Settings(audio=False, max_size=0))
        self.assertEqual(args[0], "--serial=a;echo bad")
        self.assertIn("--no-audio", args)
        self.assertFalse(any(arg.startswith("--max-size") for arg in args))

    def test_settings_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(adb_path="/路径/adb", audio=False)
            settings.save(path)
            self.assertEqual(Settings.load(path), settings)
            self.assertFalse(path.with_suffix(".tmp").exists())
            for data in ({"max_fps": 0}, {"max_size": "wrong"}, {"audio": 1}, []):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    Settings.load(path)

    def test_explicit_invalid_path_does_not_fall_back(self):
        self.assertIsNone(resolve_executable("adb", "/missing/not-an-adb"))
