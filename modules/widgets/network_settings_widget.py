"""TCP client and UDP endpoint connection fields."""
from PySide6.QtWidgets import QFormLayout, QLineEdit, QSpinBox, QWidget

from ..core.network_transport import TcpSettings, UdpSettings


class NetworkSettingsWidget(QWidget):
    def __init__(self, settings_type, parent=None):
        super().__init__(parent)
        self.settings_type = settings_type
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        udp = settings_type is UdpSettings
        self.host_edit.setAccessibleName("Bind address" if udp else "Host")
        self.port_spin.setAccessibleName("Local port" if udp else "Port")
        form.addRow("Bind address" if udp else "Host", self.host_edit)
        form.addRow("Local port" if udp else "Port", self.port_spin)
        if udp:
            self.remote_host_edit = QLineEdit()
            self.remote_host_edit.setPlaceholderText("Optional; required to send commands")
            self.remote_port_spin = QSpinBox()
            self.remote_port_spin.setRange(1, 65535)
            form.addRow("Destination host", self.remote_host_edit)
            form.addRow("Destination port", self.remote_port_spin)
        self.setFocusProxy(self.host_edit)
        self.set_settings(settings_type())

    def set_settings(self, settings):
        udp = isinstance(settings, UdpSettings)
        self.host_edit.setText(settings.bind_address if udp else settings.host)
        self.port_spin.setValue(settings.local_port if udp else settings.port)
        if udp:
            self.remote_host_edit.setText(settings.remote_host)
            self.remote_port_spin.setValue(settings.remote_port)

    def selected_settings(self):
        if self.settings_type is UdpSettings:
            settings = UdpSettings(self.host_edit.text().strip(), self.port_spin.value(),
                                   self.remote_host_edit.text().strip(), self.remote_port_spin.value())
        else:
            settings = TcpSettings(self.host_edit.text().strip(), self.port_spin.value())
        return settings
