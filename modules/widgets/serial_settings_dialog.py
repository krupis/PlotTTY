"""Small modal dialog for serial connection settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..core.serial_transport import SerialSettings


SUPPORTED_BAUD_RATES = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)


class SerialSettingsDialog(QDialog):
    def __init__(self, settings: SerialSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedWidth(360)

        self._settings = settings
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
        form = QFormLayout()
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

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.set_settings(settings)

    def selected_settings(self) -> SerialSettings:
        return SerialSettings(
            port=self._settings.port,
            baudrate=self._settings.baudrate,
            data_bits=int(self.data_bits_combo.currentData() or 8),
            parity=str(self.parity_combo.currentData() or "N"),
            stop_bits=float(self.stop_bits_combo.currentData() or 1.0),
            encoding=self.encoding_combo.currentText().strip() or "utf-8",
            line_ending=str(self.line_ending_combo.currentData() or ""),
            log_to_file=self.log_to_file_checkbox.isChecked(),
            raw_capture_mode=self.raw_capture_mode_checkbox.isChecked(),
            console_line_limit=self.console_line_limit_checkbox.isChecked(),
        )

    def set_settings(self, settings: SerialSettings) -> None:
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
