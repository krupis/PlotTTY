"""Small modal dialog for serial connection settings."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.serial_transport import SerialSettings


class SerialSettingsDialog(QDialog):
    def __init__(self, settings: SerialSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedWidth(360)

        self.port_combo = QComboBox()

        self.baud_combo = QComboBox()
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
        for encoding in ("utf-8", "ascii", "latin-1", "cp1252"):
            self.encoding_combo.addItem(encoding)

        self.line_ending_combo = QComboBox()
        for label, value in (("LF", "\n"), ("CR", "\r"), ("CRLF", "\r\n"), ("None", "")):
            self.line_ending_combo.addItem(label, value)

        log_to_file_tooltip = "Save serial text to a console log and plot values to a compressed PlotTTY capture."
        raw_capture_mode_tooltip = "Show and log raw serial data without parsing it into plot values."
        console_line_limit_tooltip = (
            "Keep only the latest console lines for smoother rendering. "
            "Disable for unlimited on-screen console history."
        )

        self.log_to_file_checkbox = QCheckBox()
        self.log_to_file_checkbox.setToolTip(log_to_file_tooltip)
        self.raw_capture_mode_checkbox = QCheckBox()
        self.raw_capture_mode_checkbox.setToolTip(raw_capture_mode_tooltip)
        self.console_line_limit_checkbox = QCheckBox()
        self.console_line_limit_checkbox.setToolTip(console_line_limit_tooltip)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.refresh_button = QPushButton("Refresh")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("green_button")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("red_button")

        port_row = QWidget()
        port_layout = QHBoxLayout(port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.setSpacing(6)
        port_layout.addWidget(self.port_combo, 1)
        port_layout.addWidget(self.refresh_button)

        form = QFormLayout()
        form.addRow("Port", port_row)
        form.addRow("Baud", self.baud_combo)
        form.addRow("Data bits", self.data_bits_combo)
        form.addRow("Parity", self.parity_combo)
        form.addRow("Stop bits", self.stop_bits_combo)
        form.addRow("Encoding", self.encoding_combo)
        form.addRow("Line ending", self.line_ending_combo)
        log_to_file_label = QLabel("Log to file")
        log_to_file_label.setToolTip(log_to_file_tooltip)
        raw_capture_mode_label = QLabel("Raw capture")
        raw_capture_mode_label.setToolTip(raw_capture_mode_tooltip)
        console_line_limit_label = QLabel("Console line limit")
        console_line_limit_label.setToolTip(console_line_limit_tooltip)
        form.addRow(log_to_file_label, self.log_to_file_checkbox)
        form.addRow(raw_capture_mode_label, self.raw_capture_mode_checkbox)
        form.addRow(console_line_limit_label, self.console_line_limit_checkbox)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        self.refresh_button.clicked.connect(self.on_refresh_ports_clicked)
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
            log_to_file=self.log_to_file_checkbox.isChecked(),
            raw_capture_mode=self.raw_capture_mode_checkbox.isChecked(),
            console_line_limit=self.console_line_limit_checkbox.isChecked(),
        )

    def selected_port(self) -> str:
        return self.port_combo.currentText().strip()

    @Slot()
    def on_refresh_ports_clicked(self) -> None:
        self.refresh_ports(self.selected_port())

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
        self.log_to_file_checkbox.setChecked(settings.log_to_file)
        self.raw_capture_mode_checkbox.setChecked(settings.raw_capture_mode)
        self.console_line_limit_checkbox.setChecked(settings.console_line_limit)


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
