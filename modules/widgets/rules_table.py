"""Plain Qt table for temporary extraction-rule edits."""
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidget, QTableWidgetItem

from ..core.extraction import ExtractionRule

RULE_MODES = {
    "auto_key_value": ("Named values", "Extract all name/value pairs, such as Voltage: 3.31."),
    "delimiter_column": ("Delimited values", "Extract a number from one zero-based field index."),
    "regex": ("Regex pattern", "The first capture group must contain the numeric value."),
    "first_number": ("First number", "Extract the first number found in each line."),
}

COLUMN_TOOLTIPS = [
    "Capture this rule as a plotted Y value.",
    "Use this rule's value as the X reference for other rules.",
    "Series label; named values use names from the incoming line.",
    "How to extract a number from each line.",
    "Regex pattern or delimiter (comma, semicolon, or \\t).",
    "Zero-based field index: 0 is the first field.",
]
EDITABLE = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable


class RulesTable(QObject):
    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)
        self._table = table
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Enable", "X reference", "Label", "Find method", "Pattern / delimiter", "Field index"])
        for column, tooltip in enumerate(COLUMN_TOOLTIPS):
            table.horizontalHeaderItem(column).setToolTip(tooltip)
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch
                                                         if column in (2, 4) else QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.setSelectionMode(table.SelectionMode.ExtendedSelection)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        self._update_columns()

    def set_rules(self, rules):
        self._table.setRowCount(0)
        for rule in rules:
            self.add_rule(rule)
        self._update_columns()

    def add_rule(self, rule=None):
        rule = rule or ExtractionRule("value", "first_number")
        row = self._table.rowCount()
        self._table.insertRow(row)
        texts = ["", "", rule.label, "", rule.delimiter.replace("\t", r"\t")
                 if rule.mode == "delimiter_column" else rule.extra_setting,
                 rule.extra_setting if rule.mode == "delimiter_column" else ""]
        for column, text in enumerate(texts):
            item = QTableWidgetItem(text)
            item.setToolTip(COLUMN_TOOLTIPS[column])
            if column < 2:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if (rule.enabled, rule.sample_counter)[column] else Qt.CheckState.Unchecked)
            self._table.setItem(row, column, item)
        self._table.item(row, 2).setData(Qt.ItemDataRole.UserRole, rule.unit)
        combo = QComboBox()
        for mode, (label, help_text) in RULE_MODES.items():
            combo.addItem(label, mode)
            combo.setItemData(combo.count() - 1, help_text, Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentIndex(combo.findData(rule.mode))
        self._table.setCellWidget(row, 3, combo)
        self._update_row(row)
        combo.currentIndexChanged.connect(lambda: self._mode_changed(combo))
        self._update_columns()

    def remove_selected_rules(self):
        rows = {index.row() for index in self._table.selectedIndexes()}
        if not rows and self._table.currentRow() >= 0:
            rows.add(self._table.currentRow())
        for row in sorted(rows, reverse=True):
            self._table.removeRow(row)
        self._update_columns()

    def rules(self):
        rules = []
        for row in range(self._table.rowCount()):
            mode = self._table.cellWidget(row, 3).currentData()
            text = [self._table.item(row, column).text().strip() for column in range(6)]
            rules.append(ExtractionRule(
                label=text[2] or "value", mode=mode,
                enabled=self._table.item(row, 0).checkState() == Qt.CheckState.Checked,
                sample_counter=self._table.item(row, 1).checkState() == Qt.CheckState.Checked,
                extra_setting=text[5] if mode == "delimiter_column" else text[4] if mode == "regex" else "",
                delimiter=text[4].replace(r"\t", "\t") if mode == "delimiter_column" else ",",
                unit=self._table.item(row, 2).data(Qt.ItemDataRole.UserRole) or "",
            ))
        return rules

    def _mode_changed(self, combo):
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 3) is combo:
                # Settings belong to a mode; start with its defaults when switching.
                self._table.item(row, 4).setText("," if combo.currentData() == "delimiter_column" else "")
                self._table.item(row, 5).setText("0" if combo.currentData() == "delimiter_column" else "")
                self._update_row(row)
                break
        self._update_columns()

    def _update_row(self, row):
        combo = self._table.cellWidget(row, 3)
        mode = combo.currentData()
        combo.setToolTip(RULE_MODES[mode][1])
        for column, applicable in ((4, mode in ("regex", "delimiter_column")), (5, mode == "delimiter_column")):
            item = self._table.item(row, column)
            item.setFlags(EDITABLE if applicable else Qt.ItemFlag.NoItemFlags)
            if not applicable:
                item.setText("")

    def _update_columns(self):
        modes = {self._table.cellWidget(row, 3).currentData() for row in range(self._table.rowCount())}
        self._table.setColumnHidden(4, not modes.intersection(("regex", "delimiter_column")))
        self._table.setColumnHidden(5, "delimiter_column" not in modes)
