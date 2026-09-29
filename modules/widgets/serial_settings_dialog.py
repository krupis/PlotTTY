"""Modal editor for advanced serial connection settings."""

from __future__ import annotations

from dataclasses import replace

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
    """Edit settings that do not belong in the main connection bar."""

    def __init__(self, settings: SerialSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced serial settings")
        self.setModal(True)
        self.setFixedWidth(360)
        self._settings = settings

        self.data_bits_combo = QComboBox()
        for value in (5, 6, 7, 8):
            self.data_bits_combo.addItem(str(value), value)

        self.parity_combo = QComboBox()
        for label, value in (("None", "N"), ("Even", "E"), ("Odd", "O"), ("Mark", "M"), ("Space", "S")):
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

        self.log_to_file_checkbox = QCheckBox()
        self.log_to_file_checkbox.setToolTip("Save serial text and extracted plot values to recording files.")
        self.raw_capture_checkbox = QCheckBox()
        self.raw_capture_checkbox.setToolTip("Show and record serial text without extracting plot values.")

        form = QFormLayout()
        form.addRow("Data bits", self.data_bits_combo)
        form.addRow("Parity", self.parity_combo)
        form.addRow("Stop bits", self.stop_bits_combo)
        form.addRow("Encoding", self.encoding_combo)
        form.addRow("Line ending", self.line_ending_combo)
        form.addRow(QLabel("Log to file"), self.log_to_file_checkbox)
        form.addRow(QLabel("Raw capture"), self.raw_capture_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.set_settings(settings)

    def selected_settings(self) -> SerialSettings:
        return replace(
            self._settings,
            data_bits=int(self.data_bits_combo.currentData() or 8),
            parity=str(self.parity_combo.currentData() or "N"),
            stop_bits=float(self.stop_bits_combo.currentData() or 1.0),
            encoding=self.encoding_combo.currentText().strip() or "utf-8",
            line_ending=str(self.line_ending_combo.currentData() or ""),
            log_to_file=self.log_to_file_checkbox.isChecked(),
            raw_capture_mode=self.raw_capture_checkbox.isChecked(),
        )

    def set_settings(self, settings: SerialSettings) -> None:
        _select_data(self.data_bits_combo, settings.data_bits)
        _select_data(self.parity_combo, settings.parity)
        _select_data(self.stop_bits_combo, settings.stop_bits)
        _select_text(self.encoding_combo, settings.encoding)
        _select_data(self.line_ending_combo, settings.line_ending)
        self.log_to_file_checkbox.setChecked(settings.log_to_file)
        self.raw_capture_checkbox.setChecked(settings.raw_capture_mode)


def _select_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def _select_text(combo: QComboBox, value: object) -> None:
    index = combo.findText(str(value))
    if index >= 0:
        combo.setCurrentIndex(index)
