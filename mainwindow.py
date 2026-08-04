# This Python file uses the following encoding: utf-8
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from time import monotonic

from PySide6.QtGui import QIcon
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QMainWindow,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.core.extraction import ExtractionEngine
from modules.core.line_decoder import LineDecoder
from modules.core.models import CapturedValue, ExtractionRule
from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.core.rule_suggestions import suggest_rules_from_samples
from modules.core.serial_log import (
    PlotSessionLog,
    SerialSessionLog,
    parse_plot_log_line,
)
from modules.core.serial_transport import SerialSettings, SerialTransport
from modules.widgets.console_widget import ConsoleWidget
from modules.widgets.loading_dialog import LoadingDialog
from modules.widgets.rules_table import RulesTable
from modules.widgets.serial_settings_dialog import SerialSettingsDialog
import resources_rc  # noqa: F401


RECEIVE_RATE_REFRESH_INTERVAL_MS = 100
RECEIVE_RATE_WINDOW_SECONDS = 1.0
STYLESHEET_PATH = Path(__file__).resolve().parent / "styles" / "application.qss"
APP_ICON_RESOURCE = ":/icons/Plottty.png"
LOAD_PROGRESS_UPDATE_ROWS = 10_000


def apply_application_style(app: QApplication) -> None:
    try:
        stylesheet = STYLESHEET_PATH.read_text(encoding="utf-8")
    except OSError:
        app.setStyleSheet("")
        return

    app.setStyleSheet(stylesheet)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(QIcon(APP_ICON_RESOURCE))

        self.transport: SerialTransport | None = None
        self.serial_settings = SerialSettings()
        self.line_decoder = LineDecoder()
        self.engine = ExtractionEngine()
        self.serial_log = SerialSessionLog()
        self.plot_log = PlotSessionLog()
        self.profile_path: Path | None = None

        self.plot = self.ui.Plot
        self._receive_rate_samples: deque[tuple[float, int]] = deque()
        self.console = ConsoleWidget(self.ui.ConsoleTextEdit, self)
        self.rules_table = RulesTable(self.ui.RulesTable, self)

        self._configure_console()
        self._configure_receive_rate_timer()
        self._connect_signals()
        self._seed_default_rules()
        self._set_connected(False)

    def _configure_console(self) -> None:
        self.ui.SendCommandTextEdit.setLineWrapMode(self.ui.SendCommandTextEdit.LineWrapMode.NoWrap)
        self.ui.SendCommandTextEdit.setPlaceholderText("Type command and press Enter")
        self.ui.SendCommandTextEdit.installEventFilter(self)

    def _configure_receive_rate_timer(self) -> None:
        self._receive_rate_timer = QTimer(self)
        self._receive_rate_timer.setInterval(RECEIVE_RATE_REFRESH_INTERVAL_MS)
        self._receive_rate_timer.timeout.connect(self.on_refresh_receive_rate_label)
        self._receive_rate_timer.start()

    def _connect_signals(self) -> None:
        self.ui.ConnectButton.clicked.connect(self.on_toggle_serial_connection)
        self.ui.pushButton.clicked.connect(self.on_open_serial_settings)
        self.ui.ClearConsoleButton.clicked.connect(self.on_clear_console_and_plot)
        self.ui.AddRuleButton.clicked.connect(self.on_add_rule)
        self.ui.RemoveRuleButton.clicked.connect(self.on_remove_selected_rules)
        self.ui.GenerateRulesButton.clicked.connect(self.on_generate_rules_from_sample)
        self.rules_table.rulesChanged.connect(self._refresh_engine)
        self.ui.actionSave_profile.triggered.connect(self.on_save_profile_as)
        self.ui.actionOpen_profile.triggered.connect(self.on_open_profile)
        self.ui.actionLoad_log.triggered.connect(self.on_load_plot_data)

    def _seed_default_rules(self) -> None:
        self.set_rules(
            [
                ExtractionRule(label="Auto key/value", mode="auto_key_value"),
            ]
        )

    def _refresh_engine(self) -> None:
        self.engine = ExtractionEngine(self.rules_table.rules())

    def on_open_profile(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(self, "Open Profile", "", "PlotTTY Profile (*.json)")
        if not path:
            return

        try:
            profile = load_profile(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Profile Failed", str(exc))
            return

        self.profile_path = Path(path)
        self.set_rules(profile.rules or [ExtractionRule(label="Auto key/value", mode="auto_key_value")])
        self.statusBar().showMessage(f"Loaded {self.profile_path.name}")

    def on_save_profile_as(self) -> None:
        default_path = str(self.profile_path or Path("profile.json"))
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Profile",
            default_path,
            "PlotTTY Profile (*.json)",
        )
        if not path:
            return

        profile = AppProfile(
            name=Path(path).stem,
            rules=self.rules_table.rules(),
        )

        try:
            save_profile(profile, path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))
            return

        self.profile_path = Path(path)
        self.statusBar().showMessage(f"Saved {self.profile_path.name}")

    def on_load_plot_data(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Load Plot Data",
            str(self.serial_log.log_dir),
            "Plot CSV (*.csv)",
        )
        if not path:
            return

        self.console.clear()
        self.plot.clear_values()
        self.console.append_status(f"[loading plot data from {Path(path).name}]\n")
        self.statusBar().showMessage(f"Loading plot data from {Path(path).name}...")
        self.console.on_flush()
        loading_dialog = LoadingDialog(f"Loading {Path(path).name}", self)
        loading_dialog.start()

        def update_load_progress(row_count: int) -> None:
            message = f"Loaded {row_count:,} rows"
            loading_dialog.set_message(message)
            self.statusBar().showMessage(message)

        try:
            captured_values, row_count = _read_plot_csv(path, update_load_progress)
            loading_dialog.set_message("Rendering plot...")
            self.plot.append_values(captured_values)
            self.plot.show_all_data()
        except Exception as exc:
            loading_dialog.close()
            QMessageBox.warning(self, "Load Plot Data Failed", str(exc))
            return

        loading_dialog.close()
        self.statusBar().showMessage(f"Loaded plot data {Path(path).name}: {row_count:,} rows")

    def on_generate_rules_from_sample(self) -> None:
        suggestions = suggest_rules_from_samples(self.ui.SampleOutputTextEdit.toPlainText())
        if not suggestions:
            self.statusBar().showMessage("No numeric values found in sample output")
            return

        rules = [suggestion.rule for suggestion in suggestions]
        self.set_rules(rules)
        self.statusBar().showMessage(f"Generated {len(rules)} rule(s) from sample output")

    def on_open_serial_settings(self) -> None:
        dialog = SerialSettingsDialog(self.serial_settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self.serial_settings = dialog.selected_settings()
        self._update_port_status_label(False)

    def on_add_rule(self) -> None:
        self.rules_table.add_rule()

    def on_remove_selected_rules(self) -> None:
        self.rules_table.remove_selected_rules()

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self.rules_table.set_rules(rules)

    def on_toggle_serial_connection(self) -> None:
        if self.transport and self.transport.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self) -> None:
        settings = self.serial_settings
        port = settings.port
        if not port:
            QMessageBox.warning(self, "No Port", "Use the Settings button and choose a serial port first.")
            return

        try:
            self.transport = SerialTransport(settings, self)
            self.line_decoder = LineDecoder(settings.encoding)
            self.transport.bytesReceived.connect(self.on_received_data)
            self.transport.errorReceived.connect(self.on_serial_error)
            self.transport.open()
        except Exception as exc:
            self.transport = None
            QMessageBox.warning(self, "Connection Failed", str(exc))
            return

        self._reset_receive_rate()
        self._set_connected(True)
        message = f"[connected to {settings.port} at {settings.baudrate} baud]"
        if settings.log_to_file:
            log_path = self.serial_log.start(settings.port, settings.baudrate)
            plot_log_path = self.plot_log.start(settings.port, settings.baudrate)
            self.serial_log.write_status(message)
            self.statusBar().showMessage(f"Logging to {log_path} and {plot_log_path}")
        else:
            self.serial_log.close()
            self.plot_log.close()
            self.statusBar().showMessage("File logging disabled")
        self.console.append_status(f"{message}\n")

    def disconnect_serial(self) -> None:
        was_connected = bool(self.transport and self.transport.is_open)
        if self.transport:
            self.transport.close()
            self.transport = None

        self._set_connected(False)
        if was_connected:
            if self.serial_settings.log_to_file:
                self.serial_log.write_status("[disconnected]")
            self.console.append_status("[disconnected]\n")
            self.serial_log.close()
            self.plot_log.close()

    def on_clear_console_and_plot(self) -> None:
        self.console.clear()
        self.plot.clear_values()
        self._reset_receive_rate()
        self.statusBar().showMessage("Cleared console and plot data")

    def on_received_data(self, data: bytes, received_at: float | None = None) -> None:
        self._record_received_bytes(len(data))
        if self.serial_settings.log_to_file:
            self.serial_log.write_received(data, self.line_decoder.encoding)
        if self.serial_settings.raw_capture_mode:
            return
        self.console.append_received(data.decode(self.line_decoder.encoding, errors="replace"))

        for line in self.line_decoder.feed(data):
            captured_values = self.engine.extract(line, timestamp=received_at)
            if captured_values:
                if self.serial_settings.log_to_file:
                    self.plot_log.write_values(captured_values)
                self.plot.append_values(captured_values)

    def on_serial_error(self, message: str) -> None:
        if self.transport and self.transport.is_open:
            self.disconnect_serial()
        QMessageBox.warning(self, "Serial Error", message)

    def on_send_command(self) -> None:
        command = self.ui.SendCommandTextEdit.toPlainText().strip()
        if not command:
            return

        if not self.transport or not self.transport.is_open:
            self.statusBar().showMessage("Connect to a serial port before sending commands")
            return

        try:
            self.transport.write_text(command)
        except Exception as exc:
            QMessageBox.warning(self, "Send Command Failed", str(exc))
            return

        self.ui.SendCommandTextEdit.clear()
        if self.serial_settings.log_to_file:
            self.serial_log.write_sent(command)
        self.console.append_sent(f"{command}\n")

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.ui.SendCommandTextEdit
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self.on_send_command()
            return True

        return super().eventFilter(watched, event)

    def _set_connected(self, connected: bool) -> None:
        self.ui.ConnectButton.setText("Disconnect" if connected else "Connect")
        self.ui.ConnectButton.setObjectName("red_button" if connected else "green_button")
        self.ui.ConnectButton.style().unpolish(self.ui.ConnectButton)
        self.ui.ConnectButton.style().polish(self.ui.ConnectButton)
        self.ui.pushButton.setEnabled(not connected)
        self.ui.SendCommandTextEdit.setEnabled(connected)
        self._update_port_status_label(connected)

    def _update_port_status_label(self, connected: bool) -> None:
        port = self.serial_settings.port or "No port"
        color = "#1f8f3a" if connected else "#c62828"
        self.ui.PortStatusLabel.setText(port)
        self.ui.PortStatusLabel.setStyleSheet(f"color: {color}; font-weight: 600;")

    def _reset_receive_rate(self) -> None:
        self._receive_rate_samples.clear()
        self.ui.DataReceivedLabel.setText("0 B/s")

    def _record_received_bytes(self, byte_count: int) -> None:
        if byte_count <= 0:
            return

        self._receive_rate_samples.append((monotonic(), byte_count))

    def on_refresh_receive_rate_label(self) -> None:
        now = monotonic()
        cutoff = now - RECEIVE_RATE_WINDOW_SECONDS
        while self._receive_rate_samples and self._receive_rate_samples[0][0] < cutoff:
            self._receive_rate_samples.popleft()

        if not self._receive_rate_samples:
            bytes_per_second = 0.0
        else:
            byte_count = sum(byte_count for _timestamp, byte_count in self._receive_rate_samples)
            bytes_per_second = byte_count / RECEIVE_RATE_WINDOW_SECONDS

        self.ui.DataReceivedLabel.setText(f"{bytes_per_second:,.0f} B/s")

    def closeEvent(self, event) -> None:
        self.console.on_flush()
        self.disconnect_serial()
        super().closeEvent(event)


def _read_plot_csv(
    path: str,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[CapturedValue], int]:
    captured_values = []
    row_count = 0
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as file:
        for line in file:
            captured = parse_plot_log_line(line.rstrip("\r\n"))
            if captured is None:
                continue

            captured_values.append(captured)
            row_count += 1
            if progress_callback is not None and row_count % LOAD_PROGRESS_UPDATE_ROWS == 0:
                progress_callback(row_count)
    return captured_values, row_count


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(APP_ICON_RESOURCE))
    apply_application_style(app)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
