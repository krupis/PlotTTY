"""Qt serial transport."""

from __future__ import annotations

from dataclasses import dataclass
from time import time

from PySide6.QtCore import QObject, Signal, Slot
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
    log_to_file: bool = True
    raw_capture_mode: bool = False
    console_line_limit: bool = True


class SerialTransport(QObject):
    bytesReceived = Signal(bytes, float)
    errorReceived = Signal(str)

    def __init__(self, settings: SerialSettings, parent: QObject | None = None):
        super().__init__(parent)
        self.settings = settings
        self._serial = QSerialPort(self)
        self._serial.readyRead.connect(self.on_ready_read)
        self._serial.errorOccurred.connect(self.on_error)

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

        data = f"{text}{self.settings.line_ending}".encode(self.settings.encoding)
        bytes_written = self._serial.write(data)
        if bytes_written == -1:
            message = self._serial.errorString() or "Could not write to serial port."
            raise RuntimeError(message)
        self._serial.flush()

    @Slot()
    def on_ready_read(self) -> None:
        received_at = time()
        data = bytes(self._serial.readAll())
        self.bytesReceived.emit(data, received_at)

    @Slot(QSerialPort.SerialPortError)
    def on_error(self, error: QSerialPort.SerialPortError) -> None:
        if error != QSerialPort.SerialPortError.NoError:
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
