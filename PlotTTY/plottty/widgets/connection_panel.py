"""Serial connection controls."""

from __future__ import annotations

from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget

from plottty.core.serial_transport import SerialSettings


class ConnectionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.port_combo = QComboBox()
        self.baud_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("ConnectButton")

        for baudrate in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            self.baud_combo.addItem(str(baudrate), baudrate)
        self.baud_combo.setCurrentText("115200")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Port"))
        layout.addWidget(self.port_combo, stretch=1)
        layout.addWidget(QLabel("Baud"))
        layout.addWidget(self.baud_combo)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.connect_button)

        self.refresh_button.clicked.connect(self.refresh_ports)
        self.refresh_ports()

    def settings(self) -> SerialSettings:
        return SerialSettings(
            port=str(self.port_combo.currentData() or ""),
            baudrate=int(self.baud_combo.currentData() or 115200),
        )

    def set_settings(self, settings: SerialSettings) -> None:
        self.refresh_ports()
        port_index = self.port_combo.findData(settings.port)
        if port_index >= 0:
            self.port_combo.setCurrentIndex(port_index)
        baud_index = self.baud_combo.findData(settings.baudrate)
        if baud_index >= 0:
            self.baud_combo.setCurrentIndex(baud_index)

    def set_connected(self, connected: bool) -> None:
        self.connect_button.setText("Disconnect" if connected else "Connect")
        self.connect_button.setProperty("connected", connected)
        self.connect_button.style().unpolish(self.connect_button)
        self.connect_button.style().polish(self.connect_button)
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.refresh_button.setEnabled(not connected)

    def refresh_ports(self) -> None:
        selected = self.port_combo.currentData()
        self.port_combo.clear()
        for port in QSerialPortInfo.availablePorts():
            label = port.portName()
            if port.description():
                label = f"{label} - {port.description()}"
            self.port_combo.addItem(label, port.portName())
        if selected:
            index = self.port_combo.findData(selected)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
