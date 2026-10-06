"""Transport selection, RTT I/O, and connection settings regressions."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from modules.controllers.connection_session import ConnectionSession, TRANSPORT_TYPES
from modules.core.extraction import ExtractionRule
from modules.core.rtt_transport import RttSettings, RttTransport
from modules.core.serial_transport import SerialSettings, SerialTransport
from modules.core.connection_settings import ConnectionSettings
from modules.core.transport import Transport
from modules.widgets.connection_settings_dialog import ConnectionSettingsDialog
from modules.widgets.serial_settings_widget import SerialSettingsWidget
from modules.widgets.rtt_settings_widget import RttSettingsWidget


APP = QApplication.instance() or QApplication([])


class FakeJLink:
    def __init__(self):
        self.chunks = deque([list(b"value: 12\n")])
        self.calls = []
        self.is_open = False

    def open(self, serial_no=None):
        self.is_open = True
        self.calls.append(("open", serial_no))

    def opened(self):
        return self.is_open

    def set_tif(self, interface):
        self.calls.append(("interface", interface))

    def connect(self, target, speed):
        self.calls.append(("connect", target, speed))

    def rtt_start(self, address):
        self.calls.append(("start", address))

    def rtt_read(self, channel, size):
        return self.chunks.popleft() if self.chunks else []

    def rtt_write(self, channel, data):
        self.calls.append(("write", channel, bytes(data)))
        return len(data)

    def rtt_stop(self):
        self.calls.append(("stop",))

    def close(self):
        self.is_open = False
        self.calls.append(("close",))


class TransportTest(unittest.TestCase):
    def test_worker_events_are_queued_to_owner_thread_in_order(self):
        deliveries = []
        transport = SerialTransport(
            SerialSettings(),
            on_bytes_received=lambda source, data, timestamp: deliveries.append(
                ("bytes", data, timestamp, QThread.currentThread())),
            on_error=lambda source, message: deliveries.append(("error", message, QThread.currentThread())),
        )
        self.addCleanup(transport.close)

        def worker():
            transport.bytesReceived.emit(transport, b"first", 123.0)
            transport.bytesReceived.emit(transport, b"second", 124.0)
            transport.errorReceived.emit(transport, "probe error")

        thread = Thread(target=worker)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(deliveries, [])
        APP.processEvents()
        self.assertEqual(deliveries, [
            ("bytes", b"first", 123.0, APP.thread()),
            ("bytes", b"second", 124.0, APP.thread()),
            ("error", "probe error", APP.thread()),
        ])

    def test_popover_selects_transport_widget_without_scanning_ports_for_rtt(self):
        settings = ConnectionSettings(transport=RttSettings(
            target="test-device", probe_serial="123", interface="JTAG", speed_khz=2000,
            control_block="0x20001000", up_channel=1, down_channel=2,
        ))
        with patch("modules.widgets.serial_settings_widget.QSerialPortInfo.availablePorts", return_value=[]) as enumerate_ports:
            dialog = ConnectionSettingsDialog(settings)
            self.addCleanup(dialog.close)
            self.assertFalse(enumerate_ports.called)
            dialog.show()
            APP.processEvents()
            self.assertIsInstance(dialog.transport_widget, RttSettingsWidget)
            self.assertFalse(dialog.transport_widgets[SerialSettings].isVisible())
            self.assertTrue(dialog.transport_widget.target_combo.isVisible())
            self.assertEqual(dialog.selected_settings(), settings)
            dialog.transport_widget.target_combo.setEditText("new-device")
            draft = dialog.selected_settings()
            self.assertIsInstance(draft.transport, RttSettings)
            self.assertEqual(draft.transport.target, "new-device")
            self.assertFalse(hasattr(draft.transport, "port"))
            self.assertEqual(settings.transport.target, "test-device")
            settings.transport = SerialSettings(
                port="COM123", baudrate=230400, data_bits=7, parity="E", stop_bits=2,
            )
            dialog.set_settings(settings)
            self.assertTrue(enumerate_ports.called)
            self.assertIsInstance(dialog.transport_widget, SerialSettingsWidget)
            self.assertTrue(dialog.transport_widget.port_combo.isVisible())
            self.assertFalse(dialog.transport_widgets[RttSettings].isVisible())
            self.assertEqual(dialog.selected_settings(), settings)

    def test_session_selects_backend(self):
        session = ConnectionSession()
        self.addCleanup(session.disconnect_device)
        for settings, backend in ((SerialSettings(), SerialTransport), (RttSettings(), RttTransport)):
            session.settings = ConnectionSettings(transport=settings, log_to_file=False)
            with patch.object(backend, "open"):
                session.connect_device()
                self.assertIsInstance(session._connection, backend)
                session.disconnect_device()

    def test_rtt_without_serial_port_receives_extracts_records_sends_and_reconnects(self):
        probe = FakeJLink()
        pylink = SimpleNamespace(JLink=lambda: probe,
                                 enums=SimpleNamespace(JLinkInterfaces=SimpleNamespace(SWD=1, JTAG=2)))
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with patch.dict("sys.modules", {"pylink": pylink}):
            session = ConnectionSession()
            self.addCleanup(session.disconnect_device)
            session.settings = ConnectionSettings(transport=RttSettings(target="test-device",
                                                  probe_serial="123", interface="JTAG",
                                                  control_block="0x20001000", down_channel=2),
                                                  encoding="latin-1", line_ending="\r\n")
            session._serial_log.log_dir = Path(directory.name)
            session._plot_log.log_dir = Path(directory.name)
            session.set_rules([ExtractionRule("value", "named_values")])
            captured, text, errors = [], [], []
            session.valuesCaptured.connect(captured.extend)
            session.receivedText.connect(text.append)
            session.errorOccurred.connect(errors.append)
            session.connect_device()
            for _ in range(100):
                if captured:
                    break
                QTest.qWait(10)
            self.assertTrue(session.is_connected)
            self.assertEqual(text, ["value: 12\n"])
            self.assertEqual(captured[0].value, 12)
            self.assertTrue(all(path.name.startswith("J-Link_RTT_test-device_") for path in session.recording_paths))
            session.send_command("READ \u00e9")
            self.assertIn(("write", 2, b"READ \xe9\r\n"), probe.calls)
            self.assertIn(("interface", 2), probe.calls)
            self.assertIn(("start", 0x20001000), probe.calls)
            session._connection.errorReceived.emit(session._connection, "probe unplugged")
            QTest.qWait(10)
            self.assertFalse(session.is_connected)
            self.assertEqual(errors, ["probe unplugged"])
            self.assertIn(("stop",), probe.calls)
            self.assertFalse(probe.is_open)
            session.connect_device()
            self.assertTrue(session.is_connected)
            session.disconnect_device()

    def test_rtt_failed_setup_closes_probe(self):
        for operation in ("connect", "rtt_start"):
            with self.subTest(operation=operation):
                probe = FakeJLink()
                pylink = SimpleNamespace(JLink=lambda: probe,
                    enums=SimpleNamespace(JLinkInterfaces=SimpleNamespace(SWD=1, JTAG=2)))
                transport = RttTransport(RttSettings(target="test-device"),
                                         on_bytes_received=lambda *_: None, on_error=lambda *_: None)
                self.addCleanup(transport.close)
                with patch.dict("sys.modules", {"pylink": pylink}), \
                        patch.object(probe, operation, side_effect=RuntimeError("setup failed")):
                    with self.assertRaisesRegex(RuntimeError, "setup failed"):
                        transport.open()
                self.assertFalse(transport.is_open)
                self.assertFalse(probe.is_open)
                self.assertIn(("close",), probe.calls)

    def test_session_uses_registered_backend_without_transport_specific_branches(self):
        class OtherTransport(Transport):
            connection_description = "Other device"
            is_open = False

            def open(self):
                self.is_open = True
                self.bytesReceived.emit(self, b"startup\n", 123.0)

            def close(self):
                super().close()
                self.is_open = False

        class OtherSettings:
            pass
        with patch.dict(TRANSPORT_TYPES, {OtherSettings: OtherTransport}):
            session = ConnectionSession()
            self.addCleanup(session.disconnect_device)
            session.settings = ConnectionSettings(transport=OtherSettings(), log_to_file=False)
            status, received, errors = [], [], []
            session.consoleText.connect(status.append)
            session.receivedText.connect(received.append)
            session.errorOccurred.connect(errors.append)
            session.connect_device()
            self.assertIsInstance(session._connection, OtherTransport)
            self.assertTrue(session.is_connected)
            self.assertIn("Other device", status[0])
            self.assertEqual(received, [])  # Startup callbacks wait for open() to finish.
            APP.processEvents()
            self.assertEqual(received, ["startup\n"])
            received.clear()
            old = session._connection
            old.bytesReceived.emit(old, b"stale\n", 124.0)
            old.errorReceived.emit(old, "stale error")
            session.disconnect_device()
            session.connect_device()
            APP.processEvents()
            self.assertEqual(received, ["startup\n"])
            self.assertEqual(errors, [])
            self.assertTrue(session.is_connected)


if __name__ == "__main__":
    unittest.main()
