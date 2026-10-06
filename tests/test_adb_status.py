import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PySide6.QtCore import QProcessEnvironment
from PySide6.QtNetwork import QTcpServer, QHostAddress
from easy_scrcpy.adb_status import AdbServerProbe, server_endpoint
from easy_scrcpy.core import Settings
from easy_scrcpy.wireless import WirelessConnection
from easy_scrcpy.wireless_ui import WirelessDialog
from test_qt import APP, wait_until


class AdbStatusTests(unittest.TestCase):
    def test_endpoint_configuration(self):
        env = QProcessEnvironment()
        self.assertEqual(server_endpoint(env), ('localhost', 5037))
        env.insert('ANDROID_ADB_SERVER_PORT', '5040')
        self.assertEqual(server_endpoint(env), ('localhost', 5040))
        env.insert('ADB_SERVER_SOCKET', 'tcp:[::1]:5041')
        self.assertEqual(server_endpoint(env), ('::1', 5041))
        for value in ('localfilesystem:/tmp/adb', 'tcp:localhost:0', 'tcp:localhost:99999'):
            env.insert('ADB_SERVER_SOCKET', value)
            with self.assertRaises(ValueError):
                server_endpoint(env)

    def test_protocol_success_invalid_timeout_and_cleanup(self):
        server = QTcpServer()
        self.assertTrue(server.listen(QHostAddress.SpecialAddress.LocalHost, 0))
        env = QProcessEnvironment()
        env.insert('ADB_SERVER_SOCKET', f'tcp:127.0.0.1:{server.serverPort()}')
        probe = AdbServerProbe()
        results = []
        probe.result.connect(lambda *args: results.append(args))
        try:
            with patch('easy_scrcpy.adb_status.tool_environment', return_value=env):
                for response, expected in ((b'OKAY00040029', True), (b'FAIL', False),
                                           (b'OKAYzzzz', False), (b'OKAY0004zzzz', False)):
                    probe.check()
                    wait_until(server.hasPendingConnections)
                    peer = server.nextPendingConnection()
                    wait_until(lambda: peer.bytesAvailable() > 0)
                    self.assertEqual(bytes(peer.readAll()), b'000Chost:version')
                    peer.write(response[:3])
                    APP.processEvents()
                    peer.write(response[3:])
                    count = len(results)
                    wait_until(lambda: len(results) > count)
                    self.assertEqual(results[-1], (expected, f'127.0.0.1:{server.serverPort()}'))
                    peer.abort()
                    peer.deleteLater()
                probe.check()
                probe.timer.start(10)
                count = len(results)
                wait_until(lambda: len(results) > count)
                self.assertFalse(results[-1][0])
                probe.check()
                probe.stop()
                self.assertFalse(probe.active)
                self.assertFalse(probe.timer.isActive())
        finally:
            probe.stop()
            server.close()

    def test_dialog_status_refresh_and_cleanup(self):
        with patch.object(WirelessConnection, 'pair_qr'), patch.object(AdbServerProbe, 'check') as check:
            dialog = WirelessDialog(SimpleNamespace(window=None, settings=Settings()))
            try:
                check.assert_called_once()
                dialog.server_checked(True, 'localhost:5040')
                self.assertIn('5040', dialog.server_status.text())
                self.assertIn('#22a447', dialog.server_dot.styleSheet())
                dialog.server_checked(False, 'localhost:5040')
                self.assertIn('#d9534f', dialog.server_dot.styleSheet())
                dialog.update_status('restarted')
                self.assertEqual(check.call_count, 2)
            finally:
                dialog.cleanup(0)
                self.assertFalse(dialog.server_refresh.isActive())
                dialog.deleteLater()
