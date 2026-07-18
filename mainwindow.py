# This Python file uses the following encoding: utf-8
import sys
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
    QTableWidgetItem,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.core.extraction import ExtractionEngine
from modules.core.line_decoder import LineDecoder
from modules.core.models import ExtractionMode, ExtractionRule
from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.core.rule_suggestions import suggest_rules_from_samples
from modules.core.serial_log import SerialLogEvent, SerialSessionLog, parse_serial_log
from modules.core.serial_transport import SerialSettings, SerialTransport
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
STYLESHEET_PATH = Path(__file__).resolve().parent / "styles" / "application.qss"


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

        self.transport: SerialTransport | None = None
        self.serial_settings = SerialSettings()
        self.line_decoder = LineDecoder()
        self.engine = ExtractionEngine()
        self.serial_log = SerialSessionLog()
        self.profile_path: Path | None = None

        self.plot = self.ui.Plot
        self._updating_rules_table = False
        self._received_byte_count = 0
        self._receive_started_at: float | None = None
        self._latest_receive_rate = 0.0
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
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.setSelectionMode(table.SelectionMode.ExtendedSelection)
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
        self.ui.actionLoad_log.triggered.connect(self.load_log_into_console)

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

    def load_log_into_console(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Load Serial Log",
            str(self.serial_log.log_dir),
            "Serial Logs (*.log);;Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            QMessageBox.warning(self, "Load Log Failed", str(exc))
            return

        self.ui.ConsoleTextEdit.document().setMaximumBlockCount(0)
        self.ui.ConsoleTextEdit.clear()
        for event in parse_serial_log(text):
            self._append_log_event(event)
        self._flush_console_text()
        self.ui.ConsoleTextEdit.moveCursor(QTextCursor.MoveOperation.Start)
        self.statusBar().showMessage(f"Loaded log {Path(path).name}")

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
        self.ui.RulesTable.setItem(row, 0, _checkbox_item(rule.enabled))
        self.ui.RulesTable.setItem(row, 1, _checkbox_item(rule.sample_counter))
        self.ui.RulesTable.setItem(row, 2, QTableWidgetItem(rule.label))
        self.ui.RulesTable.setCellWidget(row, 3, self._rule_mode_combo(rule.mode))
        self.ui.RulesTable.setItem(row, 4, QTableWidgetItem(self._extra_text_for_rule(rule)))
        self.ui.RulesTable.setItem(row, 5, QTableWidgetItem(self._position_text_for_rule(rule)))

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
        item = self.ui.RulesTable.item(row, column)
        return bool(item and item.checkState() == Qt.CheckState.Checked)

    def _handle_rule_item_changed(self, _item: QTableWidgetItem) -> None:
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
            self.serial_log.write_status(message)
            self.statusBar().showMessage(f"Logging to {log_path}")
        else:
            self.serial_log.close()
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
        self._received_byte_count = 0
        self._receive_started_at = monotonic()
        self._latest_receive_rate = 0.0
        self._refresh_receive_rate_label()

    def _record_received_bytes(self, byte_count: int) -> None:
        if byte_count <= 0:
            return

        if self._receive_started_at is None:
            self._receive_started_at = monotonic()

        self._received_byte_count += byte_count
        elapsed = max(monotonic() - self._receive_started_at, 0.001)
        self._latest_receive_rate = self._received_byte_count / elapsed

    def _refresh_receive_rate_label(self) -> None:
        self.ui.DataReceivedLabel.setText(f"{self._latest_receive_rate:,.0f} B/s")

    def _append_log_event(self, event: SerialLogEvent) -> None:
        color = _color_for_log_event(event.event_type)
        self._append_console_text(event.text, color)

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


def _checkbox_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return item


def _color_for_log_event(event_type: str) -> QColor:
    if event_type == "RX":
        return RECEIVED_TEXT_COLOR
    if event_type == "TX":
        return SENT_TEXT_COLOR
    return STATUS_TEXT_COLOR


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_application_style(app)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
