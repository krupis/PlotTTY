"""Real loopback coverage for network sessions and asynchronous lifecycle."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from time import monotonic
import unittest
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from modules.controllers.connection_session import ConnectionSession, ConnectionState
from modules.core.connection_settings import ConnectionSettings
from modules.core.extraction import ExtractionRule
from modules.core.network_transport import TcpSettings, TcpTransport, UdpSettings
from modules.widgets.connection_settings_dialog import ConnectionSettingsDialog
from qt_cleanup import delete_qt_object


APP = QApplication.instance() or QApplication([])


class NetworkTransportTest(unittest.TestCase):
    def wait_for(self, predicate):
        deadline = monotonic() + 8
        while not predicate() and monotonic() < deadline:
            QTest.qWait(5)
        self.assertTrue(predicate(), "Timed out waiting for network activity")

    def socket(self, kind=socket.SOCK_STREAM):
        endpoint = socket.socket(socket.AF_INET, kind)
        endpoint.bind(("127.0.0.1", 0))
        endpoint.setblocking(False)
        self.addCleanup(endpoint.close)
        return endpoint

    def udp_settings(self, **kwargs):
        reservation = self.socket(socket.SOCK_DGRAM)
        port = reservation.getsockname()[1]
        reservation.close()
        settings = UdpSettings(bind_address="127.0.0.1", local_port=port, **kwargs)
        return settings

    def session(self, settings, logging=False):
        session = ConnectionSession()
        self.addCleanup(delete_qt_object, session)
        self.addCleanup(session.disconnect_device)
        session.settings = ConnectionSettings(transport=settings, log_to_file=logging)
        session.set_rules([ExtractionRule("value", "named_values")])
        session.test_text, session.test_values, session.test_errors = [], [], []
        session.receivedText.connect(lambda text, timestamp: session.test_text.append(text))
        session.valuesCaptured.connect(session.test_values.extend)
        session.errorOccurred.connect(session.test_errors.append)
        return session

    def accept(self, server):
        accepted = []
        def try_accept():
            if not accepted:
                try:
                    accepted.append(server.accept()[0])
                except BlockingIOError:
                    pass
            has_peer = bool(accepted)
            return has_peer
        self.wait_for(try_accept)
        peer = accepted[0]
        peer.setblocking(False)
        self.addCleanup(peer.close)
        return peer

    def receive(self, endpoint):
        chunks = []
        def try_receive():
            try:
                chunks.append(endpoint.recv(65536))
            except BlockingIOError:
                pass
            has_data = bool(chunks)
            return has_data
        self.wait_for(try_receive)
        payload = b"".join(chunks)
        return payload

    def test_tcp_extracts_split_utf8_records_logs_sends_and_reconnects(self):
        server = self.socket()
        server.listen()
        directory = self.enterContext(TemporaryDirectory())
        session = self.session(TcpSettings("localhost", server.getsockname()[1]), logging=True)
        session._serial_log.log_dir = Path(directory)
        session._plot_log.log_dir = Path(directory)
        session.settings.line_ending = "\r\n"
        states = []
        session.stateChanged.connect(states.append)
        session.connect_device()
        self.assertTrue(session.is_connecting)
        self.assertFalse(session.is_connected)
        self.assertEqual(states, [ConnectionState.CONNECTING])
        with self.assertRaisesRegex(RuntimeError, "Connect before sending"):
            session.send_command("TOO EARLY")
        peer = self.accept(server)
        self.wait_for(lambda: session.is_connected)
        paths = session.recording_paths
        session._connection.opened.emit(session._connection)
        self.assertEqual(session.recording_paths, paths)
        self.assertEqual(states, [ConnectionState.CONNECTING, ConnectionState.CONNECTED])
        peer.sendall(b"value: 12, label: \xc3")
        self.wait_for(lambda: bool(session.test_text))
        self.assertEqual(session.test_values, [])
        peer.sendall(b"\xa9\nvalue: 13\n")
        self.wait_for(lambda: len(session.test_values) == 2)
        self.assertEqual([value.value for value in session.test_values], [12, 13])
        self.assertIn("é", "".join(session.test_text))
        session.send_command("READ é")
        self.assertEqual(self.receive(peer), "READ é\r\n".encode())
        session.disconnect_device()
        session.disconnect_device()
        self.assertEqual(states, [ConnectionState.CONNECTING, ConnectionState.CONNECTED,
                                  ConnectionState.DISCONNECTED])
        self.assertTrue(all(path.exists() for path in paths))
        self.assertIn("value: 12", paths[0].read_text(encoding="utf-8"))
        session.connect_device()
        self.accept(server)
        self.wait_for(lambda: session.is_connected)
        self.assertEqual(session.test_errors, [])

    def test_tcp_final_records_are_delivered_before_remote_close(self):
        server = self.socket()
        server.listen()
        session = self.session(TcpSettings("127.0.0.1", server.getsockname()[1]))
        session.connect_device()
        peer = self.accept(server)
        self.wait_for(lambda: session.is_connected)
        peer.sendall(b"value: 12\n" * 4000)
        peer.close()
        self.wait_for(lambda: bool(session.test_errors))
        self.assertEqual(len(session.test_values), 4000)
        self.assertFalse(session.is_connected)
        self.assertIn("closed", session.test_errors[0])

    def test_tcp_refusal_cancellation_timeout_and_stale_callbacks(self):
        reservation = self.socket()
        port = reservation.getsockname()[1]
        reservation.close()
        session = self.session(TcpSettings("127.0.0.1", port))
        session.connect_device()
        self.wait_for(lambda: bool(session.test_errors))
        self.assertFalse(session.is_connecting)
        self.assertIsNone(session._connection)
        session.test_errors.clear()
        session.connect_device()
        cancelled = session._connection
        session.disconnect_device()
        QTest.qWait(20)
        self.assertEqual(session.test_errors, [])
        self.assertFalse(session.is_connecting)
        session.connect_device()
        current = session._connection
        session._on_opened(cancelled)
        session.on_transport_error(cancelled, "stale error")
        session.on_receive(cancelled, b"value: 99\n", 123)
        self.assertIs(session._connection, current)
        current._deadline.timeout.emit()
        self.wait_for(lambda: bool(session.test_errors))
        self.assertIn("timed out", session.test_errors[0])
        self.assertEqual(session.test_values, [])

    def test_udp_receives_sends_one_datagram_and_releases_local_port(self):
        remote = self.socket(socket.SOCK_DGRAM)
        settings = self.udp_settings(remote_host="localhost", remote_port=remote.getsockname()[1])
        session = self.session(settings)
        session.connect_device()
        self.wait_for(lambda: session.is_connected)
        remote.sendto(b"value: 1\nvalue: 2\n", (settings.bind_address, settings.local_port))
        self.wait_for(lambda: len(session.test_values) == 2)
        session.send_command("READ")
        self.assertEqual(self.receive(remote), b"READ\n")
        session.disconnect_device()
        session.connect_device()
        self.wait_for(lambda: session.is_connected)
        self.assertEqual(session.test_errors, [])

    def test_udp_listener_requires_destination_to_send_and_preserves_record_delimiters(self):
        settings = self.udp_settings()
        session = self.session(settings)
        session.connect_device()
        self.assertTrue(session.is_connected)
        sender = self.socket(socket.SOCK_DGRAM)
        destination = (settings.bind_address, settings.local_port)
        sender.sendto(b"value: ", destination)
        self.wait_for(lambda: bool(session.test_text))
        self.assertEqual(session.test_values, [])
        sender.sendto(b"42\n", destination)
        self.wait_for(lambda: bool(session.test_values))
        self.assertEqual(session.test_values[0].value, 42)
        with self.assertRaisesRegex(RuntimeError, "destination"):
            session.send_command("READ")

    def test_udp_bind_failure_invalid_settings_and_async_dns_failure_clean_up(self):
        occupied = self.socket(socket.SOCK_DGRAM)
        session = self.session(UdpSettings("127.0.0.1", occupied.getsockname()[1]))
        with self.assertRaises(RuntimeError):
            session.connect_device()
        self.assertIsNone(session._connection)
        session.settings.transport = UdpSettings("not-an-address", 9000)
        with self.assertRaises(ValueError):
            session.connect_device()
        self.assertIsNone(session._connection)
        session.settings.transport = self.udp_settings(remote_host="invalid.example")
        with patch("modules.core.network_transport.QHostInfo.lookupHost", return_value=123):
            session.connect_device()
        from PySide6.QtNetwork import QHostInfo
        info = QHostInfo()
        info.setError(QHostInfo.HostInfoError.HostNotFound)
        info.setErrorString("host not found")
        session._connection._resolved(info)
        self.wait_for(lambda: bool(session.test_errors))
        self.assertFalse(session.is_connecting)
        self.assertIsNone(session._connection)

    def test_network_settings_roundtrip_without_port_scan(self):
        with patch("modules.widgets.rtt_settings_widget.RttSettingsWidget._load_targets"), \
                patch("modules.widgets.serial_settings_widget.QSerialPortInfo.availablePorts") as scan:
            for transport in (TcpSettings("device.local", 1234), UdpSettings("::", 4321, "::1", 1234)):
                settings = ConnectionSettings(transport=transport, encoding="latin-1")
                dialog = ConnectionSettingsDialog(settings)
                self.addCleanup(delete_qt_object, dialog)
                self.assertEqual(dialog.selected_settings(), settings)
                dialog.transport_widget.host_edit.setText("changed")
                self.assertEqual(dialog.selected_settings().transport, type(transport)(
                    "changed", 1234) if isinstance(transport, TcpSettings) else UdpSettings("changed", 4321, "::1", 1234))
                self.assertEqual(transport.host if isinstance(transport, TcpSettings) else transport.bind_address,
                                 "device.local" if isinstance(transport, TcpSettings) else "::")
            scan.assert_not_called()

    def test_tcp_validation_and_bounded_send_buffer(self):
        backend = TcpTransport(TcpSettings("", 9000), on_bytes_received=lambda *_: None, on_error=lambda *_: None)
        self.addCleanup(delete_qt_object, backend)
        self.addCleanup(backend.close)
        with self.assertRaises(ValueError):
            backend.open()
        with self.assertRaises(RuntimeError):
            backend.write(b"READ")
        backend.settings.host = "127.0.0.1"
        backend._ready = True
        from unittest.mock import Mock
        backend._socket = Mock()
        backend._socket.bytesToWrite.return_value = 1024 * 1024
        with self.assertRaisesRegex(RuntimeError, "buffer is full"):
            backend.write(b"READ")
        backend._socket = None

    def test_ipv6_udp_receives_and_sends(self):
        try:
            remote = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            remote.bind(("::1", 0))
        except OSError as exc:
            self.skipTest(f"IPv6 loopback unavailable: {exc}")
        self.addCleanup(remote.close)
        remote.setblocking(False)
        reservation = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        with reservation:
            reservation.bind(("::1", 0))
            local_port = reservation.getsockname()[1]
        session = self.session(UdpSettings("::1", local_port, "::1", remote.getsockname()[1]))
        session.connect_device()
        self.wait_for(lambda: session.is_connected)
        remote.sendto(b"value: 7\n", ("::1", local_port))
        self.wait_for(lambda: bool(session.test_values))
        session.send_command("READ")
        self.assertEqual(self.receive(remote), b"READ\n")
        self.assertEqual(session.test_values[0].value, 7)

    def test_udp_rejects_oversized_commands_and_wrong_destination_family(self):
        remote = self.socket(socket.SOCK_DGRAM)
        settings = self.udp_settings(remote_host="127.0.0.1", remote_port=remote.getsockname()[1])
        session = self.session(settings)
        session.connect_device()
        self.wait_for(lambda: session.is_connected)
        with self.assertRaisesRegex(ValueError, "one datagram"):
            session.send_command("x" * 65507)
        session.disconnect_device()
        session.settings.transport.remote_host = "::1"
        session.connect_device()
        self.wait_for(lambda: bool(session.test_errors))
        self.assertIn("IP family", session.test_errors[0])
        self.assertFalse(session.is_connected)

    def test_async_recording_failure_closes_network_connection(self):
        server = self.socket()
        server.listen()
        session = self.session(TcpSettings("127.0.0.1", server.getsockname()[1]), logging=True)
        states = []
        session.stateChanged.connect(states.append)
        with patch.object(session._serial_log, "start", side_effect=OSError("disk full")):
            session.connect_device()
            self.accept(server)
            self.wait_for(lambda: bool(session.test_errors))
        self.assertIn("disk full", session.test_errors[0])
        self.assertIsNone(session._connection)
        self.assertFalse(session.is_connecting)
        self.assertEqual(states, [ConnectionState.CONNECTING, ConnectionState.DISCONNECTED])


if __name__ == "__main__":
    unittest.main()
