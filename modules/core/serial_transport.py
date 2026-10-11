"""Qt serial transport."""
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from threading import Lock
from time import time
from PySide6.QtCore import QObject, QThread, QTimer, QMetaObject, Qt, Signal, Slot
from PySide6.QtSerialPort import QSerialPort
from .transport import Transport


@dataclass
class SerialSettings:
    port: str = ""
    baudrate: int = 115200
    data_bits: int = 8
    parity: str = "N"
    stop_bits: float = 1


class _SerialReader(QObject):
    dataAvailable = Signal()
    writeRequested = Signal(bytes)

    def __init__(self, transport):
        super().__init__()
        self.transport = transport
        self.serial = QSerialPort(self)
        self.serial.errorOccurred.connect(self.on_error)
        self.is_open = False
        self.open_error = ""
        self.pending = deque()
        self.lock = Lock()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(8)
        self.timer.timeout.connect(self.read_pending)
        self.writeRequested.connect(self.write_pending, Qt.ConnectionType.QueuedConnection)

    @Slot()
    def open(self):
        settings = self.transport.settings
        self.serial.setPortName(settings.port)
        self.serial.setBaudRate(settings.baudrate)
        self.serial.setDataBits(_data_bits(settings.data_bits))
        self.serial.setParity(_parity(settings.parity))
        self.serial.setStopBits(_stop_bits(settings.stop_bits))
        self.is_open = self.serial.open(QSerialPort.OpenModeFlag.ReadWrite)
        if self.is_open:
            # Drop bytes retained by the driver or an earlier USB transfer.
            self.is_open = self.serial.clear(QSerialPort.Direction.Input)
            if not self.is_open:
                self.serial.close()
        if self.is_open:
            self.timer.start()
        else:
            self.open_error = self.serial.errorString() or "Could not open serial port."

    @Slot()
    def read_pending(self):
        data = bytes(self.serial.readAll())
        if data:
            with self.lock:
                self.pending.append((data, time()))
            self.dataAvailable.emit()

    def take_pending(self):
        with self.lock:
            pending = list(self.pending)
            self.pending.clear()
        return pending

    @Slot(bytes)
    def write_pending(self, data):
        if self.serial.write(data) == -1:
            self.transport.errorReceived.emit(self.transport, self.serial.errorString())
            return
        self.serial.flush()

    @Slot()
    def close(self):
        self.timer.stop()
        if self.is_open:
            self.read_pending()
            self.serial.close()
        self.is_open = False

    @Slot(QSerialPort.SerialPortError)
    def on_error(self, error):
        if error != QSerialPort.SerialPortError.NoError:
            self.transport.errorReceived.emit(self.transport, self.serial.errorString())


class SerialTransport(Transport):
    settings: SerialSettings

    def __init__(self, settings: SerialSettings, *, on_bytes_received, on_error, parent=None):
        super().__init__(settings, on_bytes_received=on_bytes_received, on_error=on_error, parent=parent)
        # Worker notifications are queued to this GUI-owned facade. Delivering
        # its byte signal there is synchronous, avoiding a second queue hop.
        self.bytesReceived.disconnect(on_bytes_received)
        self.bytesReceived.connect(on_bytes_received, Qt.ConnectionType.AutoConnection)
        self._thread = None
        self._reader = None
        self._closing = False

    @property
    def is_open(self) -> bool:
        return bool(self._reader and self._reader.is_open)

    @property
    def connection_description(self) -> str:
        return f"Serial {self.settings.port} at {self.settings.baudrate} baud"

    def open(self) -> None:
        if not self.settings.port:
            raise RuntimeError("Choose a serial port in connection settings first.")
        if self.is_open:
            return
        self.blockSignals(False)
        self._thread = QThread(self)
        self._reader = _SerialReader(self)
        self._reader.moveToThread(self._thread)
        self._reader.dataAvailable.connect(self.deliver_pending, Qt.ConnectionType.QueuedConnection)
        self._thread.finished.connect(self._reader.deleteLater)
        self._thread.start()
        QMetaObject.invokeMethod(self._reader, 'open', Qt.ConnectionType.BlockingQueuedConnection)
        if not self.is_open:
            message = self._reader.open_error
            self.close()
            raise RuntimeError(message)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            if self._thread and self._thread.isRunning():
                QMetaObject.invokeMethod(self._reader, 'close', Qt.ConnectionType.BlockingQueuedConnection)
                self.deliver_pending()
                self._thread.quit()
                self._thread.wait()
                self._thread.deleteLater()
        finally:
            self._thread = self._reader = None
            super().close()
            self._closing = False

    def write(self, data: bytes) -> None:
        if not self.is_open:
            raise RuntimeError("Serial port is not open.")

        self._reader.writeRequested.emit(bytes(data))

    @Slot()
    def deliver_pending(self) -> None:
        if self._reader is not None:
            for data, received_at in self._reader.take_pending():
                self.bytesReceived.emit(self, data, received_at)


def _data_bits(value: int) -> QSerialPort.DataBits:
    data_bits = {
        5: QSerialPort.DataBits.Data5,
        6: QSerialPort.DataBits.Data6,
        7: QSerialPort.DataBits.Data7,
        8: QSerialPort.DataBits.Data8,
    }
    return data_bits.get(value, QSerialPort.DataBits.Data8)


def _parity(value: str) -> QSerialPort.Parity:
    parity = {
        "N": QSerialPort.Parity.NoParity,
        "E": QSerialPort.Parity.EvenParity,
        "O": QSerialPort.Parity.OddParity,
        "M": QSerialPort.Parity.MarkParity,
        "S": QSerialPort.Parity.SpaceParity,
    }
    return parity.get(value.upper(), QSerialPort.Parity.NoParity)


def _stop_bits(value: float) -> QSerialPort.StopBits:
    if value == 1.5:
        return QSerialPort.StopBits.OneAndHalfStop
    if value == 2:
        return QSerialPort.StopBits.TwoStop
    return QSerialPort.StopBits.OneStop
