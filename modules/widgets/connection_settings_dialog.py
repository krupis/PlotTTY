"""Connection settings dialog with an explicit Save boundary."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..core.connection_settings import ConnectionSettings
from ..core.serial_transport import SerialSettings
from ..core.rtt_transport import RttSettings
from ..core.network_transport import TcpSettings, UdpSettings
from .network_settings_widget import NetworkSettingsWidget
from .serial_settings_widget import SerialSettingsWidget
from .rtt_settings_widget import RttSettingsWidget


class ConnectionSettingsDialog(QDialog):
    """Edit a draft; Save applies it, while Cancel, Escape, or closing discards it."""

    def __init__(self, settings: ConnectionSettings, parent=None):
        super().__init__(parent)
        self.setObjectName("ConnectionSettingsDialog")
        self.setWindowTitle("Connection settings")
        self.setFixedWidth(390)

        self.transport_widgets = {
            SerialSettings: SerialSettingsWidget(self),
            RttSettings: RttSettingsWidget(self),
            TcpSettings: NetworkSettingsWidget(TcpSettings, self),
            UdpSettings: NetworkSettingsWidget(UdpSettings, self),
        }
        for widget in self.transport_widgets.values():
            widget.encoding_combo = QComboBox(widget)
            widget.encoding_combo.addItems(("utf-8", "ascii", "latin-1", "cp1252"))
            widget.layout().addRow("Encoding", widget.encoding_combo)

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
        layout.addWidget(self.buttons)

        self.set_settings(settings)

    def selected_settings(self) -> ConnectionSettings:
        settings = replace(
            self._settings,
            transport=self.transport_widget.selected_settings(),
            encoding=self.transport_widget.encoding_combo.currentText(),
        )
        return settings

    def set_settings(self, settings: ConnectionSettings) -> None:
        self._settings = settings
        self.transport_widget = self.transport_widgets[type(settings.transport)]
        self.transport_widget.set_settings(settings.transport)
        for widget in self.transport_widgets.values():
            widget.setVisible(widget is self.transport_widget)
        self.transport_widget.encoding_combo.setCurrentText(settings.encoding)
        self.adjustSize()
