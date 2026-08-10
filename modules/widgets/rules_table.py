"""Rules table behavior for extraction rule editing."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QObject, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidget, QTableWidgetItem

from ..core.models import ExtractionMode, ExtractionRule


MODE_LABELS: dict[str, ExtractionMode] = {
    "Named values": "auto_key_value",
    "Delimited values": "delimiter_column",
    "Regex pattern": "regex",
    "First number": "first_number",
}
MODE_NAMES_BY_VALUE = {value: label for label, value in MODE_LABELS.items()}
EDITABLE_RULE_CELL_BACKGROUND = QColor("#243840")
EDITABLE_RULE_CELL_FOREGROUND = QColor("#f3f7fb")


class RulesTable(QObject):
    rulesChanged = Signal()

    def __init__(self, table: QTableWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._table = table
        self._updating = False
        self._configure_table()
        self._table.itemChanged.connect(self.on_rule_item_changed)

    def add_rule(self, rule: ExtractionRule | None = None) -> None:
        rule = rule or ExtractionRule(label="value", mode="first_number")
        row = self._table.rowCount()
        self._updating = True
        try:
            self._table.insertRow(row)
            self._set_rule_row(row, rule)
        finally:
            self._updating = False
        self.rulesChanged.emit()

    def remove_selected_rules(self) -> None:
        rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        if not rows and self._table.currentRow() >= 0:
            rows = [self._table.currentRow()]

        for row in rows:
            self._table.removeRow(row)

        if rows:
            self.rulesChanged.emit()

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self._updating = True
        try:
            self._table.setRowCount(0)
            for rule in rules:
                row = self._table.rowCount()
                self._table.insertRow(row)
                self._set_rule_row(row, rule)
        finally:
            self._updating = False
        self.rulesChanged.emit()

    def rules(self) -> list[ExtractionRule]:
        rules = []
        for row in range(self._table.rowCount()):
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

    @Slot(object)
    def on_rule_item_changed(self, _changed: object) -> None:
        if not self._updating:
            self.rulesChanged.emit()

    @Slot()
    def on_rule_mode_changed(self) -> None:
        if not self._updating:
            self.rulesChanged.emit()

    def _configure_table(self) -> None:
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["Plot", "Use as X", "Label", "Find method", "Extra setting", "Index"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionMode(self._table.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

    def _set_rule_row(self, row: int, rule: ExtractionRule) -> None:
        self._table.setItem(row, 0, _check_item(rule.enabled))
        self._table.setItem(row, 1, _check_item(rule.sample_counter))
        self._table.setItem(row, 2, _editable_text_item(rule.label))
        self._table.setCellWidget(row, 3, self._rule_mode_combo(rule.mode))
        self._table.setItem(row, 4, _editable_text_item(self._extra_text_for_rule(rule)))
        self._table.setItem(row, 5, _editable_text_item(self._position_text_for_rule(rule)))

    def _rule_mode_combo(self, mode: ExtractionMode) -> QComboBox:
        combo = QComboBox(self._table)
        for label, value in MODE_LABELS.items():
            combo.addItem(label, value)
        combo.setCurrentText(MODE_NAMES_BY_VALUE.get(mode, "Auto key/value"))
        combo.currentIndexChanged.connect(self.on_rule_mode_changed)
        return combo

    def _rule_mode(self, row: int) -> ExtractionMode:
        combo = self._table.cellWidget(row, 3)
        if isinstance(combo, QComboBox):
            return combo.currentData()
        return "auto_key_value"

    def _rule_text(self, row: int, column: int) -> str:
        item = self._table.item(row, column)
        if item is None:
            return ""
        return item.text()

    def _rule_checked(self, row: int, column: int) -> bool:
        item = self._table.item(row, column)
        return item is not None and item.checkState() == Qt.CheckState.Checked

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


def _editable_text_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setBackground(EDITABLE_RULE_CELL_BACKGROUND)
    item.setForeground(EDITABLE_RULE_CELL_FOREGROUND)
    return item


def _check_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item
