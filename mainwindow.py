# This Python file uses the following encoding: utf-8
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path
from time import monotonic

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QTableWidgetItem,
    QWidget,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.core.extraction import ExtractionEngine
from modules.core.line_decoder import LineDecoder
from modules.core.models import CapturedValue, ExtractionMode, ExtractionRule
from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.core.rule_suggestions import suggest_rules_from_samples
from modules.core.serial_log import (
    PlotSessionLog,
    SerialSessionLog,
    parse_plot_log_line,
)
from modules.core.serial_transport import SerialSettings, SerialTransport
from modules.widgets.loading_dialog import LoadingDialog
from modules.widgets.serial_settings_dialog import SerialSettingsDialog
import resources_rc  # noqa: F401


MODE_LABELS: dict[str, ExtractionMode] = {
    "Named values": "auto_key_value",
    "Delimited values": "delimiter_column",
    "Regex pattern": "regex",
    "First number": "first_number",
}
MODE_NAMES_BY_VALUE = {value: label for label, value in MODE_LABELS.items()}
RECEIVED_TEXT_COLOR = QColor("#1f8f3a")
SENT_TEXT_COLOR = QColor("#b58900")
STATUS_TEXT_COLOR = QColor("#1f6feb")
MAX_CONSOLE_BLOCKS = 10_000
CONSOLE_FLUSH_INTERVAL_MS = 50
RECEIVE_RATE_REFRESH_INTERVAL_MS = 100
RECEIVE_RATE_WINDOW_SECONDS = 1.0
STYLESHEET_PATH = Path(__file__).resolve().parent / "styles" / "application.qss"
LOAD_PROGRESS_UPDATE_ROWS = 10_000
EDITABLE_RULE_CELL_BACKGROUND = QColor("#243840")
EDITABLE_RULE_CELL_FOREGROUND = QColor("#f3f7fb")


def apply_application_style(app: QApplication) -> None:
    try:
        stylesheet = STYLESHEET_PATH.read_text(encoding="utf-8")
    except OSError:
        app.setStyleSheet("")
        return

    app.setStyleSheet(stylesheet)


class RuleCheckCell(QWidget):
    def __init__(self, checked: bool, changed_callback: Callable[[object], None], parent: QWidget) -> None:
        super().__init__(parent)
        self.button = QPushButton(self)
        self.button.setObjectName("RuleCheckButton")
        self.button.setCheckable(True)
        self.button.setFixedSize(16, 16)
        self.button.setChecked(checked)
        self.button.toggled.connect(changed_callback)
        QTimer.singleShot(0, self._center_button)

    def is_checked(self) -> bool:
        return self.button.isChecked()

    def _center_button(self) -> None:
        self.button.move((self.width() - self.button.width()) // 2, (self.height() - self.button.height()) // 2)

    def resizeEvent(self, event) -> None:
        self._center_button()
        super().resizeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.transport: SerialTransport | None = None
        self.serial_settings = SerialSettings()
        self.line_decoder = LineDecoder()
        self.engine = ExtractionEngine()
        self.serial_log = SerialSessionLog()
        self.plot_log = PlotSessionLog()
        self.profile_path: Path | None = None

        self.plot = self.ui.Plot
        self._updating_rules_table = False
        self._receive_rate_samples: deque[tuple[float, int]] = deque()
        self._pending_console_text: list[tuple[str, QColor | None]] = []

        self._configure_console()
        self._configure_console_flush_timer()
        self._configure_receive_rate_timer()
        self._configure_rules_table()
        self._connect_signals()
        self._seed_default_rules()
        self._set_connected(False)

    def _configure_console(self) -> None:
        self.ui.ConsoleTextEdit.setReadOnly(True)
        self.ui.ConsoleTextEdit.setLineWrapMode(self.ui.ConsoleTextEdit.LineWrapMode.NoWrap)
        self.ui.ConsoleTextEdit.document().setMaximumBlockCount(MAX_CONSOLE_BLOCKS)
        self.ui.SendCommandTextEdit.setLineWrapMode(self.ui.SendCommandTextEdit.LineWrapMode.NoWrap)
        self.ui.SendCommandTextEdit.setPlaceholderText("Type command and press Enter")
        self.ui.SendCommandTextEdit.installEventFilter(self)

    def _configure_console_flush_timer(self) -> None:
        self._console_flush_timer = QTimer(self)
        self._console_flush_timer.setInterval(CONSOLE_FLUSH_INTERVAL_MS)
        self._console_flush_timer.timeout.connect(self._flush_console_text)
        self._console_flush_timer.start()

    def _configure_receive_rate_timer(self) -> None:
        self._receive_rate_timer = QTimer(self)
        self._receive_rate_timer.setInterval(RECEIVE_RATE_REFRESH_INTERVAL_MS)
        self._receive_rate_timer.timeout.connect(self._refresh_receive_rate_label)
        self._receive_rate_timer.start()

    def _configure_rules_table(self) -> None:
        table = self.ui.RulesTable
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Plot", "Use as X", "Label", "Find method", "Extra setting", "Index"]
        )
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(table.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

    def _connect_signals(self) -> None:
        self.ui.ConnectButton.clicked.connect(self.toggle_serial_connection)
        self.ui.pushButton.clicked.connect(self.open_serial_settings)
        self.ui.ClearConsoleButton.clicked.connect(self.clear_console_and_plot)
        self.ui.AddRuleButton.clicked.connect(self.add_rule)
        self.ui.RemoveRuleButton.clicked.connect(self.remove_selected_rules)
        self.ui.GenerateRulesButton.clicked.connect(self.generate_rules_from_sample)
        self.ui.RulesTable.itemChanged.connect(self._handle_rule_item_changed)
        self.ui.actionSave_profile.triggered.connect(self.save_profile_as)
        self.ui.actionOpen_profile.triggered.connect(self.open_profile)
        self.ui.actionLoad_log.triggered.connect(self.load_plot_data)

    def _seed_default_rules(self) -> None:
        self.set_rules(
            [
                ExtractionRule(label="Auto key/value", mode="auto_key_value"),
            ]
        )
        self._refresh_engine()

    def _refresh_engine(self) -> None:
        self.engine = ExtractionEngine(self.rules_from_table())

    def open_profile(self) -> None:
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

    def save_profile_as(self) -> None:
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
            rules=self.rules_from_table(),
        )

        try:
            save_profile(profile, path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))
            return

        self.profile_path = Path(path)
        self.statusBar().showMessage(f"Saved {self.profile_path.name}")

    def load_plot_data(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Load Plot Data",
            str(self.serial_log.log_dir),
            "Plot CSV (*.csv)",
        )
        if not path:
            return

        self.ui.ConsoleTextEdit.document().setMaximumBlockCount(MAX_CONSOLE_BLOCKS)
        self.ui.ConsoleTextEdit.clear()
        self.plot.clear_values()
        self._pending_console_text.clear()
        self._append_console_text(f"[loading plot data from {Path(path).name}]\n", STATUS_TEXT_COLOR)
        self.statusBar().showMessage(f"Loading plot data from {Path(path).name}...")
        self._flush_console_text()
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
            self.plot._show_all_data()
        except Exception as exc:
            loading_dialog.close()
            QMessageBox.warning(self, "Load Plot Data Failed", str(exc))
            return

        loading_dialog.close()
        self.statusBar().showMessage(f"Loaded plot data {Path(path).name}: {row_count:,} rows")

    def generate_rules_from_sample(self) -> None:
        suggestions = suggest_rules_from_samples(self.ui.SampleOutputTextEdit.toPlainText())
        if not suggestions:
            self.statusBar().showMessage("No numeric values found in sample output")
            return

        rules = [suggestion.rule for suggestion in suggestions]
        self.set_rules(rules)
        self.statusBar().showMessage(f"Generated {len(rules)} rule(s) from sample output")

    def open_serial_settings(self) -> None:
        dialog = SerialSettingsDialog(self.serial_settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self.serial_settings = dialog.selected_settings()
        self._update_port_status_label(False)

    def add_rule(self, rule: ExtractionRule | None = None) -> None:
        rule = rule or ExtractionRule(label="value", mode="first_number")
        row = self.ui.RulesTable.rowCount()
        self._updating_rules_table = True
        try:
            self.ui.RulesTable.insertRow(row)
            self._set_rule_row(row, rule)
        finally:
            self._updating_rules_table = False
        self._refresh_engine()

    def remove_selected_rules(self) -> None:
        table = self.ui.RulesTable
        rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
        if not rows and table.currentRow() >= 0:
            rows = [table.currentRow()]

        for row in rows:
            table.removeRow(row)

        if rows:
            self._refresh_engine()

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self._updating_rules_table = True
        try:
            self.ui.RulesTable.setRowCount(0)
            for rule in rules:
                row = self.ui.RulesTable.rowCount()
                self.ui.RulesTable.insertRow(row)
                self._set_rule_row(row, rule)
        finally:
            self._updating_rules_table = False
        self._refresh_engine()

    def rules_from_table(self) -> list[ExtractionRule]:
        rules = []
        for row in range(self.ui.RulesTable.rowCount()):
            mode = self._rule_mode(row)
            rules.append(
                ExtractionRule(
                    enabled=self._rule_checked(row, 0),
                    sample_counter=self._rule_checked(row, 1),
                    label=self._rule_text(row, 2).strip() or "value",
                    mode=mode,
                    extra_setting=self._extra_setting_from_row(row, mode),
                    delimiter=self._delimiter_from_row(row, mode),
                )
            )
        return rules

    def _set_rule_row(self, row: int, rule: ExtractionRule) -> None:
        self.ui.RulesTable.setCellWidget(row, 0, self._rule_checkbox(rule.enabled))
        self.ui.RulesTable.setCellWidget(row, 1, self._rule_checkbox(rule.sample_counter))
        self.ui.RulesTable.setItem(row, 2, _editable_text_item(rule.label))
        self.ui.RulesTable.setCellWidget(row, 3, self._rule_mode_combo(rule.mode))
        self.ui.RulesTable.setItem(row, 4, _editable_text_item(self._extra_text_for_rule(rule)))
        self.ui.RulesTable.setItem(row, 5, _editable_text_item(self._position_text_for_rule(rule)))

    def _rule_checkbox(self, checked: bool) -> QWidget:
        return RuleCheckCell(checked, self._handle_rule_item_changed, self.ui.RulesTable)

    def _rule_mode_combo(self, mode: ExtractionMode) -> QComboBox:
        combo = QComboBox(self.ui.RulesTable)
        for label, value in MODE_LABELS.items():
            combo.addItem(label, value)
        combo.setCurrentText(MODE_NAMES_BY_VALUE.get(mode, "Auto key/value"))
        combo.currentIndexChanged.connect(self._handle_rule_mode_changed)
        return combo

    def _rule_mode(self, row: int) -> ExtractionMode:
        combo = self.ui.RulesTable.cellWidget(row, 3)
        if isinstance(combo, QComboBox):
            return combo.currentData()
        return "auto_key_value"

    def _rule_text(self, row: int, column: int) -> str:
        item = self.ui.RulesTable.item(row, column)
        if item is None:
            return ""
        return item.text()

    def _rule_checked(self, row: int, column: int) -> bool:
        cell_widget = self.ui.RulesTable.cellWidget(row, column)
        return isinstance(cell_widget, RuleCheckCell) and cell_widget.is_checked()

    def _handle_rule_item_changed(self, _changed: object) -> None:
        if not self._updating_rules_table:
            self._refresh_engine()

    def _handle_rule_mode_changed(self) -> None:
        if not self._updating_rules_table:
            self._refresh_engine()

    def _extra_setting_from_row(self, row: int, mode: ExtractionMode) -> str:
        if mode == "delimiter_column":
            return self._rule_text(row, 5).strip()
        if mode == "regex":
            return self._rule_text(row, 4).strip()
        return ""

    def _delimiter_from_row(self, row: int, mode: ExtractionMode) -> str:
        if mode != "delimiter_column":
            return ","
        return (self._rule_text(row, 4).strip() or ",").replace(r"\t", "\t")

    def _extra_text_for_rule(self, rule: ExtractionRule) -> str:
        if rule.mode == "delimiter_column":
            return rule.delimiter.replace("\t", r"\t")
        if rule.mode == "regex":
            return rule.extra_setting
        return ""

    def _position_text_for_rule(self, rule: ExtractionRule) -> str:
        if rule.mode != "delimiter_column":
            return ""
        return rule.extra_setting

    def toggle_serial_connection(self) -> None:
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
            self.transport.bytesReceived.connect(self.handle_received_data)
            self.transport.errorReceived.connect(self.handle_serial_error)
            self.transport.open()
        except Exception as exc:
            self.transport = None
            QMessageBox.warning(self, "Connection Failed", str(exc))
            return

        # Limit the console to 2,000 lines to prevent excessive memory usage
        self.ui.ConsoleTextEdit.document().setMaximumBlockCount(MAX_CONSOLE_BLOCKS)
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
        self._append_console_text(f"{message}\n", STATUS_TEXT_COLOR)

    def disconnect_serial(self) -> None:
        was_connected = bool(self.transport and self.transport.is_open)
        if self.transport:
            self.transport.close()
            self.transport = None

        self._set_connected(False)
        if was_connected:
            if self.serial_settings.log_to_file:
                self.serial_log.write_status("[disconnected]")
            self._append_console_text("[disconnected]\n", STATUS_TEXT_COLOR)
            self.serial_log.close()
            self.plot_log.close()

    def clear_console_and_plot(self) -> None:
        self._pending_console_text.clear()
        self.ui.ConsoleTextEdit.clear()
        self.plot.clear_values()
        self._reset_receive_rate()
        self.statusBar().showMessage("Cleared console and plot data")

    def handle_received_data(self, data: bytes, received_at: float | None = None) -> None:
        self._record_received_bytes(len(data))
        if self.serial_settings.log_to_file:
            self.serial_log.write_received(data, self.line_decoder.encoding)
        if self.serial_settings.raw_capture_mode:
            return
        self._append_console_text(
            data.decode(self.line_decoder.encoding, errors="replace"),
            RECEIVED_TEXT_COLOR,
        )

        for line in self.line_decoder.feed(data):
            captured_values = self.engine.extract(line, timestamp=received_at)
            if captured_values:
                if self.serial_settings.log_to_file:
                    self.plot_log.write_values(captured_values)
                self.plot.append_values(captured_values)

    def handle_serial_error(self, message: str) -> None:
        if self.transport and self.transport.is_open:
            self.disconnect_serial()
        QMessageBox.warning(self, "Serial Error", message)

    def send_command(self) -> None:
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
        self._append_console_text(f"{command}\n", SENT_TEXT_COLOR)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.ui.SendCommandTextEdit
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self.send_command()
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

    def _refresh_receive_rate_label(self) -> None:
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

    def _append_console_text(self, text: str, color: QColor | None = None) -> None:
        if not text:
            return

        if self._pending_console_text and self._pending_console_text[-1][1] == color:
            previous_text, previous_color = self._pending_console_text[-1]
            self._pending_console_text[-1] = (previous_text + text, previous_color)
        else:
            self._pending_console_text.append((text, color))

    def _flush_console_text(self) -> None:
        if not self._pending_console_text:
            return

        pending_text = self._pending_console_text
        self._pending_console_text = []

        cursor = self.ui.ConsoleTextEdit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        for text, color in pending_text:
            text_format = QTextCharFormat()
            if color is not None:
                text_format.setForeground(color)
            cursor.insertText(text.replace("\r\n", "\n").replace("\r", "\n"), text_format)
        cursor.endEditBlock()
        self.ui.ConsoleTextEdit.setTextCursor(cursor)
        self.ui.ConsoleTextEdit.ensureCursorVisible()

    def closeEvent(self, event) -> None:
        self._flush_console_text()
        self.disconnect_serial()
        super().closeEvent(event)


def _editable_text_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setBackground(EDITABLE_RULE_CELL_BACKGROUND)
    item.setForeground(EDITABLE_RULE_CELL_FOREGROUND)
    return item


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
    apply_application_style(app)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
