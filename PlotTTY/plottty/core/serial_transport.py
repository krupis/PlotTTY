"""Qt serial transport based on QSerialPort.readyRead."""

from __future__ import annotations

from dataclasses import dataclass
from time import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtSerialPort import QSerialPort


@dataclass
class SerialSettings:
    port: str = ""
    baudrate: int = 115200
    data_bits: int = 8
    parity: str = "N"
    stop_bits: float = 1
    encoding: str = "utf-8"
    line_ending: str = "\n"


class SerialTransport(QObject):
    bytesReceived = Signal(bytes, float)
    errorReceived = Signal(str)

    def __init__(self, settings: SerialSettings, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self._serial = QSerialPort(self)
        self._serial.readyRead.connect(self._handle_ready_read)
        self._serial.errorOccurred.connect(self._handle_error)

    @property
    def is_open(self) -> bool:
        return self._serial.isOpen()

    def open(self) -> None:
        self._serial.setPortName(self.settings.port)
        self._serial.setBaudRate(self.settings.baudrate)
        self._serial.setDataBits(_data_bits(self.settings.data_bits))
        self._serial.setParity(_parity(self.settings.parity))
        self._serial.setStopBits(_stop_bits(self.settings.stop_bits))

        if not self._serial.open(QSerialPort.OpenModeFlag.ReadWrite):
            message = self._serial.errorString() or "Could not open serial port."
            raise RuntimeError(message)

    def close(self) -> None:
        if self._serial.isOpen():
            self._serial.close()

    def write_text(self, text: str) -> None:
        if not self._serial.isOpen():
            raise RuntimeError("Serial port is not open.")

        payload = text + self.settings.line_ending
        data = payload.encode(self.settings.encoding, errors="replace")
        bytes_written = self._serial.write(data)
        if bytes_written < 0:
            message = self._serial.errorString() or "Serial write failed."
            raise RuntimeError(message)

    def _handle_ready_read(self) -> None:
        received_at = time()
        data = bytes(self._serial.readAll())
        self.bytesReceived.emit(data, received_at)

    def _handle_error(self, error: QSerialPort.SerialPortError) -> None:
        if error == QSerialPort.SerialPortError.NoError:
            return
        self.errorReceived.emit(self._serial.errorString())


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
