import tempfile
from pathlib import Path
import sys
import unittest
import urllib.request
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch

from easy_scrcpy.core import Device, Presence, Settings
from easy_scrcpy.wireless import (Discovery, WirelessConnection, endpoint, classify_failure,
                                  parse_mdns, pairing_qr_payload, new_pairing_credentials)
from easy_scrcpy.wireless_ui import WirelessDialog
from test_qt import wait_until, APP

# Mimics ADB 37: pair/connect report results as text with exit code 0.
FAKE_ADB = """import sys
args = sys.argv[1:]
cmd = args[0]
if cmd == 'pair':
    print('Successfully paired to %s [guid=adb-X-abc]' % args[1] if args[2] in ('123456', 'Secret123')
          else 'Failed: Wrong password or connection was dropped.')
elif cmd == 'connect':
    print('already connected to %s' % args[1] if 'already' in sys.argv[0] else 'connected to %s' % args[1])
elif cmd == 'devices':
    print('List of devices attached')
    print('192.168.1.20:40000      device product:p model:Pixel_8 device:d transport_id:9')
    print('adb-X-abc._adb-tls-connect._tcp device product:p model:Pixel_8 device:d transport_id:10')
elif cmd == 'mdns':
    print('List of discovered mdns services')
    print('easyscrcpy-test\t_adb-tls-pairing._tcp\t192.168.1.20:41000')
    print('adb-X-abc\t_adb-tls-connect._tcp\t192.168.1.20:40000')
elif cmd in ('kill-server', 'start-server'):
    pass
"""


def fake_connection(script, calls):
    class Connection(WirelessConnection):
        def _run(self, phase, args):
            calls.append(args)
            super()._run(phase, [str(script), *args])
    return Connection(Settings())


class WirelessTests(unittest.TestCase):
    def test_failure_classification(self):
        self.assertEqual(classify_failure("failed to connect to '1.2.3.4:5': No route to host"), "network")
        self.assertEqual(classify_failure("failed to connect: Connection refused"), "refused")
        self.assertEqual(classify_failure("Failed: Wrong password or connection was dropped."), "code")
        self.assertEqual(classify_failure("failed to authenticate to 1.2.3.4:5"), "authorize")
        self.assertEqual(classify_failure("failed to connect to 1.2.3.4:5"), "unknown")

    def test_pair_passes_code_as_argument_then_connects_and_verifies(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "adb.py"
            script.write_text(FAKE_ADB, encoding="utf-8")
            calls, done = [], []
            connection = fake_connection(script, calls)
            connection.connected.connect(lambda *args: done.append(args))
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.connect_device("192.168.1.20", 40000, 41000, "123456")
                    wait_until(lambda: bool(done), timeout=10)
                self.assertEqual(calls[0], ["pair", "192.168.1.20:41000", "123456"])
                self.assertEqual(calls[1], ["devices", "-l"])
                self.assertEqual(done[0][0], "192.168.1.20:40000")
                self.assertEqual(done[0][1], "adb-X-abc")
                self.assertEqual(done[0][2], "Pixel_8")
                self.assertEqual(connection.code, "")
            finally:
                connection.shutdown()

    def test_wrong_code_reports_code_hint_and_hides_code(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "adb.py"
            script.write_text(FAKE_ADB, encoding="utf-8")
            calls, failures = [], []
            connection = fake_connection(script, calls)
            connection.failure.connect(lambda kind, detail: failures.append((kind, detail)))
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.connect_device("192.168.1.20", 40000, 41000, "654321")
                    wait_until(lambda: bool(failures))
                self.assertEqual(failures[0][0], "code")
                self.assertNotIn("654321", failures[0][1])
                self.assertEqual(len(calls), 1)
            finally:
                connection.shutdown()

    def test_ip_mode_accepts_already_connected(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "already_adb.py"
            script.write_text(FAKE_ADB, encoding="utf-8")
            calls, done = [], []
            connection = fake_connection(script, calls)
            connection.connected.connect(lambda *args: done.append(args))
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.connect_device("192.168.1.20", 40000)
                    wait_until(lambda: bool(done), timeout=10)
                self.assertEqual(calls[0], ["connect", "192.168.1.20:40000"])
            finally:
                connection.shutdown()

    def test_connect_text_failure_with_zero_exit_is_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "adb.py"
            script.write_text("print(\"failed to connect to '192.168.1.2:5555': No route to host\")\n", encoding="utf-8")
            failures, statuses = [], []
            connection = fake_connection(script, [])
            connection.failure.connect(lambda kind, detail: failures.append(kind))
            connection.status.connect(statuses.append)
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.connect_device("192.168.1.2", 5555)
                    wait_until(lambda: bool(failures))
                self.assertEqual(failures, ["network"])
                self.assertNotIn("connected", statuses)
            finally:
                connection.shutdown()

    def test_invalid_input_rejected(self):
        connection = WirelessConnection(Settings())
        try:
            for args in (("192.168.1.2", 5555, 5555, "123456"), ("192.168.1.2", 5555, 41000, "12a456"),
                         ("192.168.1.2", 5555, 41000, "12345"), ("a;bad", 5555)):
                with self.assertRaises(ValueError):
                    connection.connect_device(*args)
            self.assertFalse(connection.busy())
        finally:
            connection.shutdown()

    def test_restart_server_kills_then_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "adb.py"
            script.write_text(FAKE_ADB, encoding="utf-8")
            calls, statuses = [], []
            connection = fake_connection(script, calls)
            connection.status.connect(statuses.append)
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.restart_server()
                    wait_until(lambda: "restarted" in statuses)
                self.assertEqual(calls, [["kill-server"], ["start-server"]])
            finally:
                connection.shutdown()

    def test_disconnect_uses_only_target_transport(self):
        connection = WirelessConnection(Settings())
        try:
            with patch.object(connection, "_run") as run:
                connection.disconnect_device("192.168.1.20:40000")
                run.assert_called_once_with("disconnect", ["disconnect", "192.168.1.20:40000"])
            with patch.object(connection, "_run") as run:
                connection.disconnect_device("adb-phone._adb-tls-connect._tcp")
                self.assertEqual(run.call_args.args[1], ["disconnect", "adb-phone._adb-tls-connect._tcp"])
            for serial in ("", "emulator-5554", "usb-device", "host;bad:5555"):
                with self.assertRaises(ValueError):
                    connection.disconnect_device(serial)
        finally:
            connection.shutdown()

    def test_timeout_and_cancel_do_not_advance(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "slow.py"
            script.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
            calls = []

            class Connection(WirelessConnection):
                def _run(self, phase, args):
                    calls.append(phase)
                    super()._run(phase, [str(script)])
                    self.timer.start(100)

            connection = Connection(Settings())
            statuses = []
            connection.status.connect(statuses.append)
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.connect_device("192.168.1.20", 40000, 41000, "123456")
                    wait_until(lambda: "timeout" in statuses)
                    connection.process.waitForFinished(1000)
                    self.assertEqual(calls, ["pair"])
                    self.assertEqual(connection.code, "")
                    statuses.clear()
                    connection.connect_device("192.168.1.20", 40000)
                    connection.cancel()
                    connection.process.waitForFinished(1000)
                    self.assertNotIn("connected", statuses)
                    self.assertFalse(connection.busy())
            finally:
                connection.shutdown()

    def test_discovery_page_has_port_instructions(self):
        discovery = Discovery()
        candidates = []
        discovery.candidate.connect(candidates.append)

        class TestAddress:
            version, is_private, is_loopback, is_unspecified = 4, True, False, False

            def __str__(self):
                return "127.0.0.1"

        try:
            with patch("easy_scrcpy.wireless.ipaddress.ip_address", return_value=TestAddress()):
                url = discovery.start("192.168.1.2")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with self.assertRaises(urllib.error.HTTPError):
                opener.open(url.rsplit("/", 1)[0] + "/invalid", timeout=3)
            with opener.open(url, timeout=3) as response:
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                page = response.read().decode("utf-8")
            self.assertIn("IP: 127.0.0.1", page)
            self.assertIn("<ol>", page)
            wait_until(lambda: bool(candidates))
            with opener.open(url, timeout=3) as response:
                response.read()
            APP.processEvents()
            self.assertEqual(candidates, ["127.0.0.1"])
        finally:
            discovery.stop()
        self.assertIsNone(discovery.server)
        with self.assertRaises(ValueError):
            discovery.start("127.0.0.1")

    def test_qr_payload_matches_android_format(self):
        name, password = new_pairing_credentials()
        self.assertRegex(name, r"^easyscrcpy-[A-Za-z0-9]{8}$")
        self.assertRegex(password, r"^[A-Za-z0-9]{12}$")
        self.assertEqual(pairing_qr_payload("easyscrcpy-a", "Pw1"), "WIFI:T:ADB;S:easyscrcpy-a;P:Pw1;;")
        for bad in (("bad;name", "pw"), ("name", "p;w"), ("", "pw")):
            with self.assertRaises(ValueError):
                pairing_qr_payload(*bad)
        services = parse_mdns("List of discovered mdns services\n"
                              "adb-ZY22-H70\t_adb-tls-connect._tcp\t192.168.66.104:40747\n"
                              "studio-x _adb-tls-pairing._tcp. 192.168.66.104:41000\n"
                              "bad\t_adb-tls-connect._tcp\t127.0.0.1:1\n")
        self.assertEqual([(s.name, s.kind, s.address) for s in services],
                         [("adb-ZY22-H70", "connect", "192.168.66.104:40747"),
                          ("studio-x", "pairing", "192.168.66.104:41000")])

    def test_qr_pairing_finds_service_pairs_and_locates_guid(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "adb.py"
            script.write_text(FAKE_ADB, encoding="utf-8")
            calls, done = [], []
            connection = fake_connection(script, calls)
            connection.connected.connect(lambda *args: done.append(args))
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.pair_qr("easyscrcpy-test", "Secret123")
                    wait_until(lambda: bool(done), timeout=10)
                self.assertEqual(calls[0], ["mdns", "services"])
                self.assertEqual(calls[1], ["pair", "192.168.1.20:41000", "Secret123"])
                self.assertEqual(done[0][:2], ("adb-X-abc._adb-tls-connect._tcp", "adb-X-abc"))
            finally:
                connection.shutdown()

    def test_paired_device_uses_mdns_port(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "adb.py"
            # No auto-connected transport yet: must look up the port over mDNS, then connect.
            script.write_text(FAKE_ADB.replace(
                "    print('adb-X-abc._adb-tls-connect._tcp device", "    pass  # ('adb-X-abc._adb-tls-connect._tcp device")
                .replace("    print('192.168.1.20:40000      device", "    print('192.168.1.20:40000      device") , encoding="utf-8")
            calls, done = [], []
            connection = fake_connection(script, calls)
            connection.connected.connect(lambda *args: done.append(args))
            try:
                with patch("easy_scrcpy.wireless.resolve_executable", return_value=sys.executable):
                    connection.connect_paired("adb-X-abc")
                    wait_until(lambda: bool(done), timeout=10)
                self.assertIn(["mdns", "services"], calls)
                self.assertIn(["connect", "192.168.1.20:40000"], calls)
                self.assertEqual(done[0][0], "192.168.1.20:40000")
                with self.assertRaises(ValueError):
                    connection.connect_paired("bad;id")
            finally:
                connection.shutdown()

    def test_paired_records_validated_and_default_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "settings.json"
            settings = Settings(paired_devices=[{"guid": "adb-X-abc", "name": "Pixel 8",
                                                 "address": "192.168.1.20:40000", "paired_at": "2026-10-06T10:00:00"}])
            settings.save(path)
            self.assertEqual(Settings.load(path), settings)
            path.write_text('{"paired_devices": [{"name": "x"}]}', encoding="utf-8")
            with self.assertRaises(ValueError):
                Settings.load(path)
        with patch.object(WirelessConnection, "pair_qr") as pair_qr:
            first = WirelessDialog(SimpleNamespace(window=None, settings=Settings(), presence=SimpleNamespace(devices={})))
            try:
                self.assertEqual(first.mode.currentData(), "pair")
                pair_qr.assert_called_once()
                self.assertIsNotNone(first.pair_qr.pixmap())
            finally:
                first.cleanup(0)
                first.deleteLater()
        again = WirelessDialog(SimpleNamespace(window=None, settings=settings, presence=SimpleNamespace(devices={})))
        try:
            self.assertEqual(again.mode.currentData(), "paired")
            self.assertEqual(again.paired.currentData(), "adb-X-abc")
            self.assertFalse(again.manual_group.isVisibleTo(again))
            again.paired.setCurrentIndex(again.paired.findData(None))
            self.assertTrue(again.manual_group.isVisibleTo(again))
            with patch.object(again.discovery, "server", object()):
                again.candidate("192.168.1.20")
            self.assertEqual(again.host.text(), "192.168.1.20")
            again.connect_phone()  # empty port must not start ADB
            self.assertFalse(again.connection.busy())
            again.update_status("connect")
            self.assertFalse(again.connect_button.isEnabled())
            again.update_status("failed")
            self.assertTrue(again.connect_button.isEnabled())
            again.show_failure("code", "Failed: Wrong password")
            self.assertIn("Wrong password", again.detail.text())
            self.assertTrue(again.restart_button.isHidden())
        finally:
            again.cleanup(0)
            again.deleteLater()

    def test_endpoints_and_transport_isolation(self):
        self.assertEqual(endpoint("192.168.1.20", "5555"), "192.168.1.20:5555")
        self.assertEqual(endpoint("fd00::1", 1234), "[fd00::1]:1234")
        for host, port in (("a;bad", 5555), ("127.0.0.1", 5555), ("192.168.1.2", 0)):
            with self.assertRaises(ValueError):
                endpoint(host, port)
        presence = Presence()
        usb, wifi = Device("usb", "device", usb=True), Device("192.168.1.2:5555", "device")
        presence.update([usb, wifi])
        self.assertEqual(presence.update([wifi]), ([], {"usb"}))
        self.assertIn(wifi.serial, presence.devices)
