"""Advanced serial settings using standard Qt controls."""
from dataclasses import replace
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QVBoxLayout

SUPPORTED_BAUD_RATES = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)


def _combo(options, selected):
    combo = QComboBox()
    for label, value in options:
        combo.addItem(label, value)
    combo.setCurrentIndex(combo.findData(selected))
    return combo


class SerialSettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedWidth(360)
        self._settings = settings
        form = QFormLayout()
        self.combos = {}
        for name, label, options in (
            ("data_bits", "Data bits", [(str(n), n) for n in (5, 6, 7, 8)]),
            ("parity", "Parity", [("None", "N"), ("Even", "E"), ("Odd", "O"), ("Mark", "M"), ("Space", "S")]),
            ("stop_bits", "Stop bits", [(str(n), n) for n in (1, 1.5, 2)]),
            ("encoding", "Encoding", [(name, name) for name in ("utf-8", "ascii", "latin-1", "cp1252")]),
            ("line_ending", "Line ending", [("LF", "\n"), ("CR", "\r"), ("CRLF", "\r\n"), ("None", "")]),
        ):
            self.combos[name] = combo = _combo(options, getattr(settings, name))
            form.addRow(label, combo)
        self.log_to_file = QCheckBox("Log to file")
        self.log_to_file.setChecked(settings.log_to_file)
        self.log_to_file.setToolTip("Save serial text and compressed plot values to separate recording files.")
        self.raw_capture = QCheckBox("Raw capture")
        self.raw_capture.setChecked(settings.raw_capture_mode)
        self.raw_capture.setToolTip("Show and log serial text without extracting plot values.")
        form.addRow(self.log_to_file)
        form.addRow(self.raw_capture)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def selected_settings(self):
        return replace(self._settings, **{name: combo.currentData() for name, combo in self.combos.items()},
                       log_to_file=self.log_to_file.isChecked(), raw_capture_mode=self.raw_capture.isChecked())
