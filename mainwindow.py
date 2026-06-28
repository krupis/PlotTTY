# This Python file uses the following encoding: utf-8
import sys

from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QMainWindow,
    QPushButton,
    QTableWidgetItem,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.extraction import ExtractionEngine
from modules.line_decoder import LineDecoder
from modules.models import ExtractionMode, ExtractionRule
from modules.serial_transport import SerialSettings, SerialTransport


MODE_LABELS: dict[str, ExtractionMode] = {
    "Auto key/value": "auto_key_value",
    "First number": "first_number",
    "Regex": "regex",
    "Delimiter column": "delimiter_column",
}
MODE_NAMES_BY_VALUE = {value: label for label, value in MODE_LABELS.items()}


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.transport: SerialTransport | None = None
        self.line_decoder = LineDecoder()
        self.engine = ExtractionEngine()

        self.plot = self.ui.Plot
        self._updating_rules_table = False
        self.port_combo = QComboBox(self)
        self.baud_combo = QComboBox(self)
        self.refresh_ports_button = QPushButton("Refresh", self)

        self._install_connection_controls()
        self._configure_console()
        self._configure_rules_table()
        self._connect_signals()
        self._seed_default_rules()
        self._set_connected(False)

    def _install_connection_controls(self) -> None:
        self.port_combo.setEditable(True)
        self.port_combo.setMinimumWidth(180)

        for baudrate in (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600):
            self.baud_combo.addItem(str(baudrate), baudrate)
        self.baud_combo.setCurrentText("115200")

        self.ui.TopNavBar.replaceWidget(self.ui.plainTextEdit, self.port_combo)
        self.ui.plainTextEdit.deleteLater()

        connect_button_index = self.ui.TopNavBar.indexOf(self.ui.ConnectButton)
        self.ui.TopNavBar.insertWidget(connect_button_index, QLabel("Baud:", self))
        self.ui.TopNavBar.insertWidget(connect_button_index + 1, self.baud_combo)
        self.ui.TopNavBar.insertWidget(connect_button_index + 2, self.refresh_ports_button)

        self.refresh_ports()

    def _configure_console(self) -> None:
        self.ui.ConsoleTextEdit.setReadOnly(True)
        self.ui.ConsoleTextEdit.setLineWrapMode(self.ui.ConsoleTextEdit.LineWrapMode.NoWrap)
        self.ui.ConsoleTextEdit.document().setMaximumBlockCount(2_000)

    def _configure_rules_table(self) -> None:
        table = self.ui.RulesTable
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Enable", "Use as X counter", "Label", "Find method", "Extra setting", "Position"]
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
        self.refresh_ports_button.clicked.connect(self.refresh_ports)
        self.ui.ConnectButton.clicked.connect(self.connect_serial)
        self.ui.DisconnectButton.clicked.connect(self.disconnect_serial)
        self.ui.AddRuleButton.clicked.connect(self.add_rule)
        self.ui.RemoveRuleButton.clicked.connect(self.remove_selected_rules)
        self.ui.RulesTable.itemChanged.connect(self._handle_rule_item_changed)

    def _seed_default_rules(self) -> None:
        self.set_rules(
            [
                ExtractionRule(label="Auto key/value", mode="auto_key_value"),
            ]
        )
        self._refresh_engine()

    def _refresh_engine(self) -> None:
        self.engine = ExtractionEngine(self.rules_from_table())

    def add_rule(self, rule: ExtractionRule | None = None) -> None:
        rule = rule or ExtractionRule(label="value", mode="first_number")
        row = self.ui.RulesTable.rowCount()
        self.ui.RulesTable.insertRow(row)
        self._set_rule_row(row, rule)
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
        self.ui.RulesTable.setRowCount(0)
        for rule in rules:
            row = self.ui.RulesTable.rowCount()
            self.ui.RulesTable.insertRow(row)
            self._set_rule_row(row, rule)
        self._updating_rules_table = False
        self._refresh_engine()

    def rules_from_table(self) -> list[ExtractionRule]:
        rules = []
        for row in range(self.ui.RulesTable.rowCount()):
            rules.append(
                ExtractionRule(
                    enabled=self._rule_checked(row, 0),
                    sample_counter=self._rule_checked(row, 1),
                    label=self._rule_text(row, 2).strip() or "value",
                    mode=self._rule_mode(row),
                    extra_setting=self._rule_text(row, 4).strip(),
                    delimiter=self._rule_text(row, 5).strip() or ",",
                )
            )
        return rules

    def _set_rule_row(self, row: int, rule: ExtractionRule) -> None:
        self._updating_rules_table = True
        self.ui.RulesTable.setItem(row, 0, _checkbox_item(rule.enabled))
        self.ui.RulesTable.setItem(row, 1, _checkbox_item(rule.sample_counter))
        self.ui.RulesTable.setItem(row, 2, QTableWidgetItem(rule.label))
        self.ui.RulesTable.setCellWidget(row, 3, self._rule_mode_combo(rule.mode))
        self.ui.RulesTable.setItem(row, 4, QTableWidgetItem(rule.extra_setting))
        self.ui.RulesTable.setItem(row, 5, QTableWidgetItem(rule.delimiter))
        self._updating_rules_table = False

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

    def refresh_ports(self) -> None:
        selected_port = self._selected_port()
        self.port_combo.clear()

        for port in QSerialPortInfo.availablePorts():
            label = port.portName()
            if port.description():
                label = f"{label} - {port.description()}"
            self.port_combo.addItem(label, port.portName())

        if selected_port:
            index = self.port_combo.findData(selected_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
            else:
                self.port_combo.setEditText(selected_port)

    def connect_serial(self) -> None:
        port = self._selected_port()
        if not port:
            QMessageBox.warning(self, "No Port", "Enter a serial port first.")
            return

        baudrate = int(self.baud_combo.currentData() or 115200)
        settings = SerialSettings(port=port, baudrate=baudrate)
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

        self._set_connected(True)
        self._append_console_text(f"[connected to {port} at {baudrate} baud]\n")
        self.statusBar().showMessage(f"Connected to {port} at {baudrate} baud")

    def disconnect_serial(self) -> None:
        was_connected = bool(self.transport and self.transport.is_open)
        if self.transport:
            self.transport.close()
            self.transport = None

        self._set_connected(False)
        if was_connected:
            self._append_console_text("[disconnected]\n")
        self.statusBar().showMessage("Disconnected")

    def handle_received_data(self, data: bytes, received_at: float | None = None) -> None:
        self._append_console_text(data.decode(self.line_decoder.encoding, errors="replace"))

        for line in self.line_decoder.feed(data):
            captured_values = self.engine.extract(line, timestamp=received_at)
            if captured_values:
                self.plot.append_values(captured_values)

    def handle_serial_error(self, message: str) -> None:
        if self.transport and self.transport.is_open:
            self.disconnect_serial()
        QMessageBox.warning(self, "Serial Error", message)

    def _set_connected(self, connected: bool) -> None:
        self.ui.ConnectButton.setEnabled(not connected)
        self.ui.DisconnectButton.setEnabled(connected)
        self.port_combo.setEnabled(not connected)
        self.baud_combo.setEnabled(not connected)
        self.refresh_ports_button.setEnabled(not connected)

    def _selected_port(self) -> str:
        return str(self.port_combo.currentData() or self.port_combo.currentText()).strip()

    def _append_console_text(self, text: str) -> None:
        if not text:
            return

        self.ui.ConsoleTextEdit.moveCursor(QTextCursor.MoveOperation.End)
        self.ui.ConsoleTextEdit.insertPlainText(text.replace("\r\n", "\n").replace("\r", "\n"))
        self.ui.ConsoleTextEdit.ensureCursorVisible()

    def closeEvent(self, event) -> None:
        self.disconnect_serial()
        super().closeEvent(event)


def _checkbox_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    return item


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
