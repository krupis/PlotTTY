"""J-Link RTT connection fields and settings."""

from PySide6.QtWidgets import QComboBox, QFormLayout, QLineEdit, QSpinBox, QWidget

from ..core.rtt_transport import RttSettings


class RttSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_edit = QLineEdit()
        self.target_edit.setPlaceholderText("e.g. STM32G474VE")
        self.probe_edit = QLineEdit()
        self.probe_edit.setPlaceholderText("Automatic probe")
        self.interface_combo = QComboBox()
        self.interface_combo.addItems(("SWD", "JTAG"))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(5, 12000)
        self.speed_spin.setSuffix(" kHz")
        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText("Auto-detect")
        self.up_spin = QSpinBox()
        self.up_spin.setRange(0, 255)
        self.down_spin = QSpinBox()
        self.down_spin.setRange(0, 255)

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("RTT target", self.target_edit)
        form.addRow("J-Link probe serial", self.probe_edit)
        form.addRow("Debug interface", self.interface_combo)
        form.addRow("Interface speed", self.speed_spin)
        form.addRow("RTT control block", self.address_edit)
        form.addRow("RTT up channel", self.up_spin)
        form.addRow("RTT down channel", self.down_spin)
        self.setFocusProxy(self.target_edit)

    def selected_settings(self) -> RttSettings:
        return RttSettings(
            target=self.target_edit.text().strip(),
            probe_serial=self.probe_edit.text().strip(),
            interface=self.interface_combo.currentText(),
            speed_khz=self.speed_spin.value(),
            control_block=self.address_edit.text().strip(),
            up_channel=self.up_spin.value(),
            down_channel=self.down_spin.value(),
        )

    def set_settings(self, settings: RttSettings) -> None:
        self.target_edit.setText(settings.target)
        self.probe_edit.setText(settings.probe_serial)
        self.interface_combo.setCurrentText(settings.interface)
        self.speed_spin.setValue(settings.speed_khz)
        self.address_edit.setText(settings.control_block)
        self.up_spin.setValue(settings.up_channel)
        self.down_spin.setValue(settings.down_channel)
