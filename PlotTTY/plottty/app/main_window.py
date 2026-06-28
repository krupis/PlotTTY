"""Main PlotTTY window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from plottty.core.extraction import ExtractionEngine
from plottty.core.line_decoder import LineDecoder
from plottty.core.profiles import PlotTTYProfile, load_profile, save_profile
from plottty.core.serial_transport import SerialTransport
from plottty.widgets.captured_values_widget import CapturedValuesWidget
from plottty.widgets.command_panel import CommandPanel
from plottty.widgets.connection_panel import ConnectionPanel
from plottty.widgets.console_widget import ConsoleWidget
from plottty.widgets.extraction_rules_widget import ExtractionRulesWidget
from plottty.widgets.plot_widget import PlotWidget


STATS_REFRESH_INTERVAL_MS = 1_000


class PlotTTYMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlotTTY")
        self.resize(1180, 760)

        self.transport: SerialTransport | None = None
        self.line_decoder = LineDecoder()
        self.engine = ExtractionEngine()
        self.profile_path: Path | None = None
        self._received_bytes_since_stats_update = 0

        self.connection_panel = ConnectionPanel()
        self.console = ConsoleWidget()
        self.command_panel = CommandPanel()
        self.captured_values = CapturedValuesWidget()
        self.plot = PlotWidget()
        self.rules = ExtractionRulesWidget()
        self.status_label = QLabel("Disconnected")
        self.status_label.setObjectName("StatusLabel")
        self.stats_label = QLabel("0 B/s")
        self.stats_label.setObjectName("StatsLabel")
        self.console_output_button = QPushButton("Console On")
        self.console_output_button.setCheckable(True)
        self.console_output_button.setChecked(True)
        self.console_output_button.setToolTip("Enable or disable serial console rendering.")

        self._stats_timer = QTimer(self)
        self._stats_timer.setInterval(STATS_REFRESH_INTERVAL_MS)
        self._stats_timer.timeout.connect(self._refresh_receive_statistics)

        self._build_ui()
        self._connect_signals()
        self._refresh_engine()

    def _build_ui(self) -> None:
        toolbar_widget = QWidget()
        toolbar_widget.setObjectName("TopBar")
        toolbar = QHBoxLayout(toolbar_widget)
        toolbar.setContentsMargins(12, 10, 12, 10)
        toolbar.addWidget(self.connection_panel, stretch=1)
        toolbar.addWidget(self.status_label)

        left_tabs = QTabWidget()
        left_tabs.setMinimumWidth(220)
        left_tabs.addTab(self.console, "Console")
        left_tabs.addTab(self.rules, "Rules")

        splitter = QSplitter()
        splitter.addWidget(left_tabs)

        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(320)
        right_tabs.addTab(self.captured_values, "Values")
        right_tabs.addTab(self.plot, "Plot")

        splitter.addWidget(right_tabs)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([520, 660])

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_session)

        bottom = QHBoxLayout()
        bottom.addWidget(self.command_panel, stretch=1)
        bottom.addWidget(self.stats_label)
        bottom.addWidget(self.console_output_button)
        bottom.addWidget(clear_button)

        page = QWidget()
        page.setObjectName("CentralPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(toolbar_widget)
        layout.addWidget(splitter, stretch=1)
        layout.addLayout(bottom)
        self.setCentralWidget(page)

        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Open Profile...", self.open_profile)
        file_menu.addAction("Save Profile As...", self.save_profile_as)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

    def _connect_signals(self) -> None:
        self.connection_panel.connect_button.clicked.connect(self.toggle_connection)
        self.command_panel.sendRequested.connect(self.send_command)
        self.rules.rulesChanged.connect(self._refresh_engine)
        self.console_output_button.toggled.connect(self._set_console_output_enabled)

    def toggle_connection(self) -> None:
        if self.transport and self.transport.is_open:
            self.disconnect_serial()
            return

        settings = self.connection_panel.settings()
        if not settings.port:
            QMessageBox.warning(self, "No Port", "Select a serial port first.")
            return
        try:
            self.transport = SerialTransport(settings)
            self.line_decoder = LineDecoder(settings.encoding)
            self._reset_receive_statistics()
            self.transport.open()
            self.transport.bytesReceived.connect(self.handle_received_data)
            self.transport.errorReceived.connect(self.handle_serial_error)
        except Exception as exc:
            self.transport = None
            QMessageBox.warning(self, "Connection Failed", str(exc))
            return

        self.connection_panel.set_connected(True)
        self.status_label.setText(f"Connected to {settings.port}")

    def disconnect_serial(self) -> None:
        if self.transport:
            self.transport.close()
        self.connection_panel.set_connected(False)
        self.status_label.setText("Disconnected")
        self._reset_receive_statistics()

    def handle_received_data(self, data: bytes, received_at: float | None = None) -> None:
        self._record_received_bytes(len(data))
        if self.console_output_button.isChecked():
            # Append data to the console (pending_segments will handle the actual rendering).
            self.console.append(data, "rx", self.line_decoder.encoding)

        for line in self.line_decoder.feed(data):
            captured_values = self.engine.extract(line, timestamp=received_at)
            if captured_values:
                self.captured_values.append_values(captured_values)
                self.plot.append_values(captured_values)

    def handle_serial_error(self, message: str) -> None:
        if self.transport and self.transport.is_open:
            self.disconnect_serial()
        QMessageBox.warning(self, "Serial Error", message)

    def send_command(self, command: str) -> None:
        if not self.transport or not self.transport.is_open:
            QMessageBox.warning(self, "Not Connected", "Connect to a serial port before sending.")
            return
        try:
            self.transport.write_text(command)
            if self.console_output_button.isChecked():
                self.console.append(command + self.transport.settings.line_ending, "tx")
        except Exception as exc:
            QMessageBox.warning(self, "Send Failed", str(exc))

    def clear_session(self) -> None:
        self.captured_values.clear_values()
        self.plot.clear_values()
        self.console.clear()
        self._reset_receive_statistics()

    def open_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Profile", "", "PlotTTY Profile (*.json)")
        if not path:
            return
        profile = load_profile(path)
        self.profile_path = Path(path)
        self.connection_panel.set_settings(profile.serial)
        self.command_panel.set_commands(profile.commands)
        self.rules.set_rules(profile.rules)
        self.status_label.setText(f"Loaded {profile.name}")

    def save_profile_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Profile", "", "PlotTTY Profile (*.json)")
        if not path:
            return
        profile = PlotTTYProfile(
            serial=self.connection_panel.settings(),
            commands=self.command_panel.commands(),
            rules=self.rules.rules(),
        )
        save_profile(profile, path)
        self.profile_path = Path(path)
        self.status_label.setText(f"Saved {self.profile_path.name}")

    def _refresh_engine(self) -> None:
        self.engine = ExtractionEngine(self.rules.rules())

    def _set_console_output_enabled(self, enabled: bool) -> None:
        self.console_output_button.setText("Console On" if enabled else "Console Off")

    def _record_received_bytes(self, byte_count: int) -> None:
        self._received_bytes_since_stats_update += byte_count
        if not self._stats_timer.isActive():
            self._stats_timer.start()

    def _reset_receive_statistics(self) -> None:
        self._received_bytes_since_stats_update = 0
        self._stats_timer.stop()
        self.stats_label.setText("0 B/s")

    def _refresh_receive_statistics(self) -> None:
        bytes_per_second = self._received_bytes_since_stats_update
        self._received_bytes_since_stats_update = 0
        self.stats_label.setText(f"{bytes_per_second:,} B/s")
        if bytes_per_second == 0:
            self._stats_timer.stop()

    def closeEvent(self, event) -> None:
        self.disconnect_serial()
        super().closeEvent(event)
