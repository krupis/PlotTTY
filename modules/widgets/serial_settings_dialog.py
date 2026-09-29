"""Connection settings popover with an explicit Save boundary."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPoint, Qt
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.serial_transport import SerialSettings


SUPPORTED_BAUD_RATES = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)


class SerialSettingsDialog(QDialog):
    """Edit a draft; Escape or clicking outside dismisses it without saving."""

    def __init__(self, settings: SerialSettings, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("ConnectionPopover")
        self.setWindowTitle("Connection settings")
        self.setFixedWidth(390)
        self._settings = settings
        self._anchor = None

        self.port_combo = QComboBox()
        self.port_combo.setPlaceholderText("Select port")
        self.port_combo.setAccessibleName("Serial port")
        self.refresh_button = QPushButton("Rescan")
        self.refresh_button.clicked.connect(self.refresh_ports)
        port_row = QHBoxLayout()
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
        form.addRow("Port", port_row)
        form.addRow("Baud rate", self.baud_combo)
        form.addRow("Data bits", self.data_bits_combo)
        form.addRow("Parity", self.parity_combo)
        form.addRow("Stop bits", self.stop_bits_combo)
        form.addRow("Encoding", self.encoding_combo)
        form.addRow("Line ending", self.line_ending_combo)
        capture = QFormLayout()
        capture.addRow("Record to file", self.log_to_file_checkbox)
        capture.addRow("Raw capture", self.raw_capture_checkbox)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save settings")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        heading = QLabel("Connection")
        heading.setObjectName("ConnectionHeading")
        layout.addWidget(heading)
        layout.addLayout(form)
        self.capture_toggle = self._add_section(layout, "Capture options", capture)
        layout.addWidget(self.buttons)

        self.set_settings(settings)

    def selected_settings(self) -> SerialSettings:
        return replace(
            self._settings,
            port=self.port_combo.currentText(),
            baudrate=int(self.baud_combo.currentText()),
            data_bits=int(self.data_bits_combo.currentData() or 8),
            parity=str(self.parity_combo.currentData() or "N"),
            stop_bits=float(self.stop_bits_combo.currentData() or 1.0),
            encoding=self.encoding_combo.currentText().strip() or "utf-8",
            line_ending=str(self.line_ending_combo.currentData() or ""),
            log_to_file=self.log_to_file_checkbox.isChecked(),
            raw_capture_mode=self.raw_capture_checkbox.isChecked(),
        )

    def set_settings(self, settings: SerialSettings) -> None:
        self._settings = replace(settings)
        self.refresh_ports(settings.port)
        if self.baud_combo.findText(str(settings.baudrate)) < 0:
            self.baud_combo.addItem(str(settings.baudrate))
        _select_text(self.baud_combo, str(settings.baudrate))
        _select_data(self.data_bits_combo, settings.data_bits)
        _select_data(self.parity_combo, settings.parity)
        _select_data(self.stop_bits_combo, settings.stop_bits)
        _select_text(self.encoding_combo, settings.encoding)
        _select_data(self.line_ending_combo, settings.line_ending)
        self.log_to_file_checkbox.setChecked(settings.log_to_file)
        self.raw_capture_checkbox.setChecked(settings.raw_capture_mode)

    def refresh_ports(self, selected=None) -> None:
        # A clicked(bool) signal must preserve the current draft selection.
        if not isinstance(selected, str):
            selected = self.port_combo.currentText()
        self.port_combo.clear()
        for port in QSerialPortInfo.availablePorts():
            self.port_combo.addItem(port.portName())
            self.port_combo.setItemData(self.port_combo.count() - 1, port.description(), Qt.ItemDataRole.ToolTipRole)
        if selected and self.port_combo.findText(selected) < 0:
            self.port_combo.addItem(selected)
        self.port_combo.setCurrentIndex(self.port_combo.findText(selected) if selected else -1)

    def _add_section(self, layout, title, form):
        toggle = QToolButton()
        toggle.setObjectName("SettingsSection")
        toggle.setText(title)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setCheckable(True)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        body = QWidget()
        body.setLayout(form)
        body.hide()
        layout.addWidget(toggle)
        layout.addWidget(body)

        def expand(checked):
            body.setVisible(checked)
            toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
            self.adjustSize()
            self._position()

        toggle.toggled.connect(expand)
        return toggle

    def show_below(self, anchor):
        self._anchor = anchor
        self.adjustSize()
        self._position()
        self.show()
        self.port_combo.setFocus()

    def _position(self):
        if self._anchor is None:
            return
        origin = self._anchor.mapToGlobal(QPoint(0, self._anchor.height() + 4))
        available = self._anchor.screen().availableGeometry()
        x = max(available.left(), min(origin.x(), available.right() - self.width() + 1))
        y = max(available.top(), min(origin.y(), available.bottom() - self.height() + 1))
        self.move(x, y)


def _select_data(combo: QComboBox, value: object) -> None:
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


def _select_text(combo: QComboBox, value: object) -> None:
    index = combo.findText(str(value))
    if index >= 0:
        combo.setCurrentIndex(index)
