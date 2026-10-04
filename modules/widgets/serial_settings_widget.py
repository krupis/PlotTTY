"""Serial connection fields and settings."""

from PySide6.QtCore import Qt
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QPushButton, QWidget

from ..core.serial_transport import SerialSettings


SUPPORTED_BAUD_RATES = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)


class SerialSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.port_combo = QComboBox()
        self.port_combo.setPlaceholderText("Select port")
        self.port_combo.setAccessibleName("Serial port")
        self.refresh_button = QPushButton("Rescan")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row = QHBoxLayout()
        port_row.setContentsMargins(0, 0, 0, 0)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_button)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems([str(value) for value in SUPPORTED_BAUD_RATES])
        self.baud_combo.setMaxVisibleItems(len(SUPPORTED_BAUD_RATES))
        self.data_bits_combo = QComboBox()
        for value in (5, 6, 7, 8):
            self.data_bits_combo.addItem(str(value), value)
        self.parity_combo = QComboBox()
        for label, value in (("None", "N"), ("Even", "E"), ("Odd", "O"), ("Mark", "M"), ("Space", "S")):
            self.parity_combo.addItem(label, value)
        self.stop_bits_combo = QComboBox()
        for label, value in (("1", 1.0), ("1.5", 1.5), ("2", 2.0)):
            self.stop_bits_combo.addItem(label, value)

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Port", port_row)
        form.addRow("Baud rate", self.baud_combo)
        form.addRow("Data bits", self.data_bits_combo)
        form.addRow("Parity", self.parity_combo)
        form.addRow("Stop bits", self.stop_bits_combo)
        self.setFocusProxy(self.port_combo)

    def selected_settings(self) -> SerialSettings:
        return SerialSettings(
            port=self.port_combo.currentText(),
            baudrate=int(self.baud_combo.currentText()),
            data_bits=self.data_bits_combo.currentData(),
            parity=self.parity_combo.currentData(),
            stop_bits=self.stop_bits_combo.currentData(),
        )

    def set_settings(self, settings: SerialSettings) -> None:
        self.port_combo.clear()
        if settings.port:
            self.port_combo.addItem(settings.port)
            self.port_combo.setCurrentIndex(0)
        self.refresh_ports()
        if self.baud_combo.findText(str(settings.baudrate)) < 0:
            self.baud_combo.addItem(str(settings.baudrate))
        self.baud_combo.setCurrentText(str(settings.baudrate))
        self.data_bits_combo.setCurrentIndex(self.data_bits_combo.findData(settings.data_bits))
        self.parity_combo.setCurrentIndex(self.parity_combo.findData(settings.parity))
        self.stop_bits_combo.setCurrentIndex(self.stop_bits_combo.findData(settings.stop_bits))

    def refresh_ports(self) -> None:
        selected = self.port_combo.currentText()
        self.port_combo.clear()
        for port in QSerialPortInfo.availablePorts():
            self.port_combo.addItem(port.portName())
            self.port_combo.setItemData(self.port_combo.count() - 1, port.description(), Qt.ItemDataRole.ToolTipRole)
        if selected and self.port_combo.findText(selected) < 0:
            self.port_combo.addItem(selected)
        self.port_combo.setCurrentIndex(self.port_combo.findText(selected) if selected else -1)
