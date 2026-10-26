"""Serial input drains on disconnect and supports writes and reopening."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from qt_cleanup import delete_qt_object
from time import sleep
from unittest.mock import patch
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtSerialPort import QSerialPort
from PySide6.QtWidgets import QApplication
from modules.controllers.connection_session import ConnectionSession
from modules.core.extraction import ExtractionRule
from modules.core.serial_transport import SerialSettings, SerialTransport

APP = QApplication.instance() or QApplication([])


class FakeSerial(QObject):
    errorOccurred = Signal(QSerialPort.SerialPortError)
    OpenModeFlag = QSerialPort.OpenModeFlag
    SerialPortError = QSerialPort.SerialPortError
    Direction = QSerialPort.Direction
    DataBits, Parity, StopBits = QSerialPort.DataBits, QSerialPort.Parity, QSerialPort.StopBits
    fail_open = False
    fail_write = False
    fail_clear = False
    startup_data = b''

    def __init__(self, parent):
        super().__init__(parent)
        self.incoming = self.startup_data
        self.writes = []
        self.opened = False

    def setPortName(self, value): pass
    def setBaudRate(self, value): pass
    def setDataBits(self, value): pass
    def setParity(self, value): pass
    def setStopBits(self, value): pass
    def open(self, flags):
        self.opened = not self.fail_open
        return self.opened
    def isOpen(self): return self.opened
    def errorString(self): return 'fake failure'
    def readAll(self):
        assert QThread.currentThread() is self.thread()
        data, self.incoming = self.incoming, b''
        return data
    def write(self, data):
        assert QThread.currentThread() is self.thread()
        if self.fail_write:
            return -1
        self.writes.append(bytes(data))
        return len(data)
    def flush(self): pass
    def clear(self, directions):
        assert QThread.currentThread() is self.thread()
        assert directions == self.Direction.Input
        self.incoming = b''
        return not self.fail_clear
    def close(self): self.opened = False


class SerialAcquisitionTest(unittest.TestCase):
    def test_reads_during_gui_pause_and_disconnect_drains_before_teardown(self):
        session = ConnectionSession()
        self.addCleanup(delete_qt_object, session)
        session.settings.transport = SerialSettings(port='FAKE')
        session.settings.log_to_file = False
        session.set_rules([ExtractionRule('Named', 'named_values')])
        received, captured = [], []
        session.receivedText.connect(received.append)
        session.valuesCaptured.connect(captured.extend)
        with patch('modules.core.serial_transport.QSerialPort', FakeSerial):
            session.connect_device()
            serial = session._connection._reader.serial
            serial.incoming = b'v: 1\n'
            sleep(.025)
            self.assertEqual(captured, [])
            serial.incoming = b'v: 2\npartial'
            sleep(.025)
            session.disconnect_device()
            self.assertEqual(''.join(received), 'v: 1\nv: 2\npartial')
            self.assertEqual([value.value for value in captured], [1, 2])
            self.assertFalse(serial.isOpen())
            APP.processEvents()
            self.assertEqual(len(captured), 2)

    def test_failed_open_write_errors_and_reopen(self):
        deliveries = []
        errors = []
        with patch('modules.core.serial_transport.QSerialPort', FakeSerial):
            backend = SerialTransport(SerialSettings(port='FAKE'),
                on_bytes_received=lambda _, data, __: deliveries.append(data),
                on_error=lambda _, message: errors.append(message))
            with patch.object(FakeSerial, 'fail_open', True):
                with self.assertRaisesRegex(RuntimeError, 'fake failure'):
                    backend.open()
            with patch.object(FakeSerial, 'fail_clear', True):
                with self.assertRaisesRegex(RuntimeError, 'fake failure'):
                    backend.open()
            backend.open()
            serial = backend._reader.serial
            backend.write(b'CMD,ping\n')
            backend.close()
            self.assertEqual(serial.writes, [b'CMD,ping\n'])
            backend.open()
            with patch.object(FakeSerial, 'fail_write', True):
                backend.write(b'bad')
                backend.close()
            APP.processEvents()
            self.assertEqual(errors, ['fake failure'])
            with self.assertRaisesRegex(RuntimeError, 'not open'):
                backend.write(b'closed')
            backend.open()
            backend._reader.serial.incoming = b'reopened\n'
            sleep(.025)
            APP.processEvents()
            self.assertEqual(deliveries, [b'reopened\n'])
            backend.close()

    def test_open_discards_stale_input_and_preserves_new_input(self):
        deliveries = []
        with patch('modules.core.serial_transport.QSerialPort', FakeSerial), \
                patch.object(FakeSerial, 'startup_data', b'old session\n'):
            backend = SerialTransport(SerialSettings(port='FAKE'),
                on_bytes_received=lambda _, data, __: deliveries.append(data),
                on_error=lambda *_: None)
            backend.open()
            serial = backend._reader.serial
            self.assertEqual(serial.incoming, b'')
            serial.incoming = b'new session\n'
            backend.close()
            self.assertEqual(deliveries, [b'new session\n'])
