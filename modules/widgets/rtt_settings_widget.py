"""J-Link RTT connection fields and settings."""

from threading import Thread

from PySide6.QtCore import QSignalBlocker, QStringListModel, Qt, Signal, Slot
from PySide6.QtWidgets import QComboBox, QCompleter, QFormLayout, QLabel, QLineEdit, QSpinBox, QWidget

from ..core.rtt_transport import RttSettings


class RttSettingsWidget(QWidget):
    targetsLoaded = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._targets_loading = False
        self._targets_loaded = False
        self.target_combo = QComboBox()
        self.target_combo.setEditable(True)
        self.target_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.target_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.target_combo.setMinimumContentsLength(12)
        self.target_combo.setMaxVisibleItems(12)
        self.target_combo.setAccessibleName("RTT target device")
        self.target_combo.lineEdit().setPlaceholderText("Search MCU name…")
        self.target_model = QStringListModel(self)
        self.target_combo.setModel(self.target_model)
        completer = self.target_combo.completer()
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setMaxVisibleItems(12)
        self.target_hint = QLabel("Type to search supported devices")
        self.target_hint.setObjectName("ConnectionDetails")
        self.target_hint.setWordWrap(True)
        self.targetsLoaded.connect(self._on_targets_loaded, Qt.ConnectionType.QueuedConnection)
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
        form.addRow("RTT target", self.target_combo)
        form.addRow(self.target_hint)
        form.addRow("J-Link probe serial", self.probe_edit)
        form.addRow("Debug interface", self.interface_combo)
        form.addRow("Interface speed", self.speed_spin)
        form.addRow("RTT control block", self.address_edit)
        form.addRow("RTT up channel", self.up_spin)
        form.addRow("RTT down channel", self.down_spin)
        self.setFocusProxy(self.target_combo)

    def selected_settings(self) -> RttSettings:
        return RttSettings(
            target=self.target_combo.currentText().strip(),
            probe_serial=self.probe_edit.text().strip(),
            interface=self.interface_combo.currentText(),
            speed_khz=self.speed_spin.value(),
            control_block=self.address_edit.text().strip(),
            up_channel=self.up_spin.value(),
            down_channel=self.down_spin.value(),
        )

    def set_settings(self, settings: RttSettings) -> None:
        self.target_combo.setEditText(settings.target)
        self.probe_edit.setText(settings.probe_serial)
        self.interface_combo.setCurrentText(settings.interface)
        self.speed_spin.setValue(settings.speed_khz)
        self.address_edit.setText(settings.control_block)
        self.up_spin.setValue(settings.up_channel)
        self.down_spin.setValue(settings.down_channel)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._targets_loaded and not self._targets_loading:
            self._targets_loading = True
            self.target_hint.setText("Loading supported devices…")
            Thread(target=self._load_targets, name="RTT-device-catalog", daemon=True).start()

    def _load_targets(self):
        try:
            import pylink
            jlink = pylink.JLink()
            # This queries the installed DLL's catalog without opening a probe.
            names = sorted({jlink.supported_device(index).name
                            for index in range(jlink.num_supported_devices())}, key=str.casefold)
            error = ""
        except Exception as exc:
            names, error = [], str(exc)
        try:
            self.targetsLoaded.emit(names, error)
        except RuntimeError:
            pass  # The widget may have been destroyed while the catalog was loading.

    @Slot(list, str)
    def _on_targets_loaded(self, names, error):
        self._targets_loading = False
        if error or not names:
            self.target_hint.setText("Device list unavailable. You can enter a target name manually.")
            self.target_hint.setToolTip(error or "The installed J-Link library returned no devices.")
            return
        self._targets_loaded = True
        text = self.target_combo.currentText()
        with QSignalBlocker(self.target_combo):
            self.target_model.setStringList(names)
            self.target_combo.setCurrentIndex(-1)
            self.target_combo.setEditText(text)
        self.target_hint.setText(f"{len(names):,} devices · type to filter")
        self.target_hint.setToolTip("Supported-device list from the installed J-Link software.")
