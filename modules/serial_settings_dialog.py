"""Small modal dialog for serial connection settings."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
)

from .serial_transport import SerialSettings


class SerialSettingsDialog(QDialog):
    def __init__(self, settings: SerialSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Serial Port Settings")
        self.setModal(True)
        self.setFixedWidth(360)

        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)

        self.baud_combo = QComboBox()
        self.baud_combo.setEditable(True)
        self.baud_combo.setValidator(QIntValidator(1, 4_000_000, self))
        for baudrate in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            self.baud_combo.addItem(str(baudrate))

        self.data_bits_combo = QComboBox()
        for data_bits in (5, 6, 7, 8):
            self.data_bits_combo.addItem(str(data_bits), data_bits)

        self.parity_combo = QComboBox()
        for label, value in (
            ("None", "N"),
            ("Even", "E"),
            ("Odd", "O"),
            ("Mark", "M"),
            ("Space", "S"),
        ):
            self.parity_combo.addItem(label, value)

        self.stop_bits_combo = QComboBox()
        for label, value in (("1", 1.0), ("1.5", 1.5), ("2", 2.0)):
            self.stop_bits_combo.addItem(label, value)

        self.encoding_combo = QComboBox()
        self.encoding_combo.setEditable(True)
        for encoding in ("utf-8", "ascii", "latin-1", "cp1252"):
            self.encoding_combo.addItem(encoding)

        self.line_ending_combo = QComboBox()
        for label, value in (("LF", "\n"), ("CR", "\r"), ("CRLF", "\r\n"), ("None", "")):
            self.line_ending_combo.addItem(label, value)

        self.refresh_button = QPushButton("Refresh Ports")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        form = QFormLayout()
        form.addRow("Port", self.port_combo)
        form.addRow("", self.refresh_button)
        form.addRow("Baud", self.baud_combo)
        form.addRow("Data bits", self.data_bits_combo)
        form.addRow("Parity", self.parity_combo)
        form.addRow("Stop bits", self.stop_bits_combo)
        form.addRow("Encoding", self.encoding_combo)
        form.addRow("Line ending", self.line_ending_combo)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        self.refresh_button.clicked.connect(lambda: self.refresh_ports(self.selected_port()))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.refresh_ports(settings.port)
        self.set_settings(settings)

    def selected_settings(self) -> SerialSettings:
        return SerialSettings(
            port=self.selected_port(),
            baudrate=int(self.baud_combo.currentText() or 115200),
            data_bits=int(self.data_bits_combo.currentData() or 8),
            parity=str(self.parity_combo.currentData() or "N"),
            stop_bits=float(self.stop_bits_combo.currentData() or 1.0),
            encoding=self.encoding_combo.currentText().strip() or "utf-8",
            line_ending=str(self.line_ending_combo.currentData() or ""),
        )

    def selected_port(self) -> str:
        return self.port_combo.currentText().strip()

    def refresh_ports(self, selected_port: str = "") -> None:
        self.port_combo.clear()
        for port in QSerialPortInfo.availablePorts():
            self.port_combo.addItem(port.portName())
            if port.description():
                self.port_combo.setItemData(
                    self.port_combo.count() - 1,
                    port.description(),
                    Qt.ItemDataRole.ToolTipRole,
                )

        if selected_port:
            _select_text(self.port_combo, selected_port)

    def set_settings(self, settings: SerialSettings) -> None:
        _select_text(self.port_combo, settings.port)
        _select_text(self.baud_combo, str(settings.baudrate))
        _select_data(self.data_bits_combo, settings.data_bits)
        _select_data(self.parity_combo, settings.parity)
        _select_data(self.stop_bits_combo, settings.stop_bits)
        _select_text(self.encoding_combo, settings.encoding)
        _select_data(self.line_ending_combo, settings.line_ending)


def _select_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def _select_text(combo: QComboBox, value: object) -> None:
    text = str(value)
    index = combo.findText(text)
    if index >= 0:
        combo.setCurrentIndex(index)
    elif combo.isEditable():
        combo.setEditText(text)
