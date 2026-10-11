"""Connection settings popover with an explicit Save boundary."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..core.connection_settings import ConnectionSettings
from ..core.serial_transport import SerialSettings
from ..core.rtt_transport import RttSettings
from .serial_settings_widget import SerialSettingsWidget
from .rtt_settings_widget import RttSettingsWidget


class ConnectionSettingsDialog(QDialog):
    """Edit a draft; Escape or clicking outside dismisses it without saving."""

    def __init__(self, settings: ConnectionSettings, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("ConnectionPopover")
        self.setWindowTitle("Connection settings")
        self.setFixedWidth(390)
        self._anchor = None

        self.transport_widgets = {
            SerialSettings: SerialSettingsWidget(self),
            RttSettings: RttSettingsWidget(self),
        }

        self.encoding_combo = QComboBox()
        for encoding in ("utf-8", "ascii", "latin-1", "cp1252"):
            self.encoding_combo.addItem(encoding)

        self.line_ending_combo = QComboBox()
        for label, value in (("LF", "\n"), ("CR", "\r"), ("CRLF", "\r\n"), ("None", "")):
            self.line_ending_combo.addItem(label, value)

        form = QFormLayout()
        form.addRow("Encoding", self.encoding_combo)
        form.addRow("Line ending", self.line_ending_combo)

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
        for widget in self.transport_widgets.values():
            layout.addWidget(widget)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        self.set_settings(settings)

    def selected_settings(self) -> ConnectionSettings:
        return replace(
            self._settings,
            transport=self.transport_widget.selected_settings(),
            encoding=self.encoding_combo.currentText().strip() or "utf-8",
            line_ending=str(self.line_ending_combo.currentData() or ""),
        )

    def set_settings(self, settings: ConnectionSettings) -> None:
        self._settings = settings
        self.transport_widget = self.transport_widgets[type(settings.transport)]
        self.transport_widget.set_settings(settings.transport)
        for widget in self.transport_widgets.values():
            widget.setVisible(widget is self.transport_widget)
        self.encoding_combo.setCurrentText(settings.encoding)
        self.line_ending_combo.setCurrentIndex(self.line_ending_combo.findData(settings.line_ending))

    def show_below(self, anchor):
        self._anchor = anchor
        self.adjustSize()
        self._position()
        self.show()
        self.transport_widget.setFocus()

    def _position(self):
        if self._anchor is None:
            return
        origin = self._anchor.mapToGlobal(QPoint(0, self._anchor.height() + 4))
        available = self._anchor.screen().availableGeometry()
        x = max(available.left(), min(origin.x(), available.right() - self.width() + 1))
        y = max(available.top(), min(origin.y(), available.bottom() - self.height() + 1))
        self.move(x, y)
