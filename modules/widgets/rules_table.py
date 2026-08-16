"""Rules table behavior for extraction rule editing."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QObject, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QHeaderView, QStyledItemDelegate, QStyleOptionViewItem, QTableWidget, QTableWidgetItem

from ..core.models import ExtractionMode, ExtractionRule


MODE_LABELS: dict[str, ExtractionMode] = {
    "Named values": "auto_key_value",
    "Delimited values": "delimiter_column",
    "Regex pattern": "regex",
    "First number": "first_number",
}
MODE_NAMES_BY_VALUE = {value: label for label, value in MODE_LABELS.items()}
MODE_HELP: dict[ExtractionMode, str] = {
    "auto_key_value": "Extracts all name/value pairs, such as Voltage: 3.31 or current=0.14.",
    "delimiter_column": "Splits each line by a delimiter, then extracts the number from one zero-based field index.",
    "regex": "Uses a regular expression. The first capture group must be the numeric value.",
    "first_number": "Extracts the first number found in each line.",
}
COLUMN_TOOLTIPS = [
    "Draw this rule as a plotted Y value.",
    "Use this rule's value as the X axis timestamp/counter for the other plotted rules.",
    "Name used for the plotted series. Named values can override this with names from the input line.",
    "How this rule finds a value in each incoming line.",
    "Delimited values: delimiter to split on, such as comma, semicolon, or \\t. Regex pattern: regular expression.",
    "Delimited values only: field index after splitting the line. 0 is first, 1 is second.",
]
PATTERN_DELIMITER_COLUMN = 4
COLUMN_NUMBER_COLUMN = 5
EDITABLE_RULE_CELL_BACKGROUND = QColor("#243840")
EDITABLE_RULE_CELL_FOREGROUND = QColor("#f3f7fb")
EDITABLE_RULE_CELL_BORDER = QColor("#5fa88f")
INACTIVE_RULE_CELL_BACKGROUND = QColor("#20262d")
INACTIVE_RULE_CELL_FOREGROUND = QColor("#7f8994")
INACTIVE_CELL_TEXT = "N/A"


class RulesTable(QObject):
    rulesChanged = Signal()

    def __init__(self, table: QTableWidget, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._table = table
        self._updating = False
        self._configure_table()
        self._table.setItemDelegate(RuleCellDelegate(self._table))
        self._update_method_column_visibility()
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
        self._update_method_column_visibility()
        self.rulesChanged.emit()

    def remove_selected_rules(self) -> None:
        rows = sorted({index.row() for index in self._table.selectedIndexes()}, reverse=True)
        if not rows and self._table.currentRow() >= 0:
            rows = [self._table.currentRow()]

        for row in rows:
            self._table.removeRow(row)

        if rows:
            self._update_method_column_visibility()
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
        self._update_method_column_visibility()
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
        combo = self.sender()
        if isinstance(combo, QComboBox):
            combo.setToolTip(MODE_HELP.get(combo.currentData(), "Choose how to extract a number from each incoming line."))
            was_updating = self._updating
            self._updating = True
            try:
                self._update_method_cells(self._row_for_widget(combo))
                self._update_method_column_visibility()
            finally:
                self._updating = was_updating
        if not self._updating:
            self.rulesChanged.emit()

    def _configure_table(self) -> None:
        self._table.setColumnCount(6)
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
        self._table.setItem(row, 0, _check_item(rule.enabled, COLUMN_TOOLTIPS[0]))
        self._table.setItem(row, 1, _check_item(rule.sample_counter, COLUMN_TOOLTIPS[1]))
        self._table.setItem(row, 2, _editable_text_item(rule.label, COLUMN_TOOLTIPS[2]))
        self._table.setCellWidget(row, 3, self._rule_mode_combo(rule.mode))
        self._table.setItem(row, 4, _editable_text_item(self._extra_text_for_rule(rule), COLUMN_TOOLTIPS[4]))
        self._table.setItem(row, 5, _editable_text_item(self._position_text_for_rule(rule), COLUMN_TOOLTIPS[5]))
        self._update_method_cells(row)

    def _rule_mode_combo(self, mode: ExtractionMode) -> QComboBox:
        combo = QComboBox(self._table)
        for label, value in MODE_LABELS.items():
            combo.addItem(label, value)
            combo.setItemData(combo.count() - 1, MODE_HELP[value], Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentText(MODE_NAMES_BY_VALUE.get(mode, "Named values"))
        combo.setToolTip(MODE_HELP.get(mode, "Choose how to extract a number from each incoming line."))
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

    def _row_for_widget(self, widget: QComboBox) -> int:
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 3) is widget:
                return row
        return -1

    def _update_method_cells(self, row: int) -> None:
        if row < 0:
            return

        mode = self._rule_mode(row)
        self._prepare_method_cell_values(row, mode)
        self._set_cell_applicable(
            row,
            PATTERN_DELIMITER_COLUMN,
            mode in ("delimiter_column", "regex"),
            _setting_tooltip_for_mode(mode),
        )
        self._set_cell_applicable(
            row,
            COLUMN_NUMBER_COLUMN,
            mode == "delimiter_column",
            COLUMN_TOOLTIPS[COLUMN_NUMBER_COLUMN],
        )

    def _prepare_method_cell_values(self, row: int, mode: ExtractionMode) -> None:
        setting_item = self._table.item(row, PATTERN_DELIMITER_COLUMN)
        column_item = self._table.item(row, COLUMN_NUMBER_COLUMN)
        if setting_item is None or column_item is None:
            return

        setting_text = setting_item.text().strip()
        column_text = column_item.text().strip()
        if setting_text == INACTIVE_CELL_TEXT:
            setting_text = ""
            setting_item.setText("")
        if column_text == INACTIVE_CELL_TEXT:
            column_text = ""
            column_item.setText("")
        if mode == "delimiter_column":
            if not setting_text:
                setting_item.setText(",")
            if not column_text:
                column_item.setText("0")
        elif mode == "regex":
            if setting_text in (",", ";", r"\t"):
                setting_item.setText("")
            column_item.setText("")
        else:
            setting_item.setText("")
            column_item.setText("")

    def _set_cell_applicable(self, row: int, column: int, applicable: bool, tooltip: str) -> None:
        item = self._table.item(row, column)
        if item is None:
            return

        if applicable:
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            item.setBackground(EDITABLE_RULE_CELL_BACKGROUND)
            item.setForeground(EDITABLE_RULE_CELL_FOREGROUND)
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(tooltip)
        else:
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setText(INACTIVE_CELL_TEXT)
            item.setBackground(INACTIVE_RULE_CELL_BACKGROUND)
            item.setForeground(INACTIVE_RULE_CELL_FOREGROUND)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip("Not used by the selected find method.")

    def _update_method_column_visibility(self) -> None:
        modes = [self._rule_mode(row) for row in range(self._table.rowCount())]
        uses_pattern_or_delimiter = any(mode in ("delimiter_column", "regex") for mode in modes)
        uses_column_number = any(mode == "delimiter_column" for mode in modes)
        self._table.setColumnHidden(PATTERN_DELIMITER_COLUMN, not uses_pattern_or_delimiter)
        self._table.setColumnHidden(COLUMN_NUMBER_COLUMN, not uses_column_number)


def _editable_text_item(text: str, tooltip: str = "") -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
    item.setBackground(EDITABLE_RULE_CELL_BACKGROUND)
    item.setForeground(EDITABLE_RULE_CELL_FOREGROUND)
    if tooltip:
        item.setToolTip(tooltip)
    return item


def _check_item(checked: bool, tooltip: str = "") -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
    item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if tooltip:
        item.setToolTip(tooltip)
    return item


def _setting_tooltip_for_mode(mode: ExtractionMode) -> str:
    if mode == "delimiter_column":
        return "Delimiter used to split each incoming line, such as comma, semicolon, or \\t."
    if mode == "regex":
        return "Regular expression used to find the value. The first capture group must be numeric."
    return "Not used by the selected find method."


class RuleCellDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        editable = bool(index.flags() & Qt.ItemFlag.ItemIsEditable)
        enabled = bool(index.flags() & Qt.ItemFlag.ItemIsEnabled)
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)

        if editable:
            style_option.backgroundBrush = EDITABLE_RULE_CELL_BACKGROUND
        elif not enabled:
            style_option.backgroundBrush = INACTIVE_RULE_CELL_BACKGROUND

        super().paint(painter, style_option, index)

        if editable:
            painter.save()
            painter.setPen(QPen(EDITABLE_RULE_CELL_BORDER))
            painter.drawRect(option.rect.adjusted(2, 2, -3, -3))
            painter.restore()
