"""Plain Qt table for temporary extraction-rule edits."""
from PySide6.QtCore import QObject, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidget, QTableWidgetItem

from ..core.extraction import ExtractionRule

RULE_MODES = {
    "auto_key_value": ("Named values", "Extract all name/value pairs, such as Voltage: 3.31."),
    "delimiter_column": ("Delimited values", "Extract a number from one zero-based field index."),
    "regex": ("Regex pattern", "The first capture group must contain the numeric value."),
    "first_number": ("First number", "Extract the first number found in each line."),
}

RULE_FUNCTIONS = {
    "plot": ("Plot", "Capture this value as a plotted series."),
    "time": ("Time", "Use this value as the timestamp for the other plotted values."),
}

COLUMN_TOOLTIPS = [
    "Plot captures a series; Time uses this value as the timestamp for other series.",
    "Series label; named values use names from the incoming line.",
    "How to extract a number from each line.",
    "Regex pattern or delimiter (comma, semicolon, or \\t).",
    "Zero-based field index: 0 is the first field.",
]
EDITABLE = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable


class RulesTable(QObject):
    rulesChanged = Signal()

    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)
        self._table = table
        self._setting_rules = False
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Function", "Label", "Find method", "Pattern / delimiter", "Field index"])
        for column, tooltip in enumerate(COLUMN_TOOLTIPS):
            table.horizontalHeaderItem(column).setToolTip(tooltip)
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch
                                                         if column in (1, 3) else QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().hide()
        table.setAlternatingRowColors(True)
        table.setSelectionMode(table.SelectionMode.ExtendedSelection)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        self._update_columns()

    def set_rules(self, rules):
        self._setting_rules = True
        try:
            self._table.setRowCount(0)
            for rule in rules:
                self.add_rule(rule)
            self._update_columns()
        finally:
            self._setting_rules = False
        self.rulesChanged.emit()

    def add_rule(self, rule=None):
        rule = rule or ExtractionRule("value", "first_number")
        blocker = QSignalBlocker(self._table)
        row = self._table.rowCount()
        self._table.insertRow(row)
        texts = ["", rule.label, "", rule.delimiter.replace("\t", r"\t")
                 if rule.mode == "delimiter_column" else rule.extra_setting,
                 rule.extra_setting if rule.mode == "delimiter_column" else ""]
        for column, text in enumerate(texts):
            item = QTableWidgetItem(text)
            item.setToolTip(COLUMN_TOOLTIPS[column])
            self._table.setItem(row, column, item)
        self._table.item(row, 1).setData(Qt.ItemDataRole.UserRole, rule.unit)
        function = QComboBox()
        for value, (label, help_text) in RULE_FUNCTIONS.items():
            function.addItem(label, value)
            function.setItemData(function.count() - 1, help_text, Qt.ItemDataRole.ToolTipRole)
        function.setCurrentIndex(function.findData("time" if rule.sample_counter else "plot"))
        self._table.setCellWidget(row, 0, function)
        combo = QComboBox()
        for mode, (label, help_text) in RULE_MODES.items():
            combo.addItem(label, mode)
            combo.setItemData(combo.count() - 1, help_text, Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentIndex(combo.findData(rule.mode))
        self._table.setCellWidget(row, 2, combo)
        self._update_row(row)
        combo.currentIndexChanged.connect(lambda: self._mode_changed(combo))
        function.currentIndexChanged.connect(lambda: self._function_changed(function))
        self._function_changed(function)
        self._update_columns()
        del blocker
        if not self._setting_rules:
            self.rulesChanged.emit()

    def remove_selected_rules(self):
        rows = {index.row() for index in self._table.selectedIndexes()}
        if not rows and self._table.currentRow() >= 0:
            rows.add(self._table.currentRow())
        for row in sorted(rows, reverse=True):
            self._table.removeRow(row)
        self._update_columns()
        self.rulesChanged.emit()

    def rules(self):
        rules = []
        for row in range(self._table.rowCount()):
            mode = self._table.cellWidget(row, 2).currentData()
            text = [self._table.item(row, column).text().strip() for column in (1, 3, 4)]
            rules.append(ExtractionRule(
                label=text[0] or "value", mode=mode,
                sample_counter=self._table.cellWidget(row, 0).currentData() == "time",
                extra_setting=text[2] if mode == "delimiter_column" else text[1] if mode == "regex" else "",
                delimiter=text[1].replace(r"\t", "\t") if mode == "delimiter_column" else ",",
                unit=self._table.item(row, 1).data(Qt.ItemDataRole.UserRole) or "",
            ))
        return rules

    def _mode_changed(self, combo):
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 2) is combo:
                # Settings belong to a mode; start with its defaults when switching.
                self._table.item(row, 3).setText("," if combo.currentData() == "delimiter_column" else "")
                self._table.item(row, 4).setText("0" if combo.currentData() == "delimiter_column" else "")
                self._update_row(row)
                break
        self._update_columns()
        self.rulesChanged.emit()

    def _function_changed(self, combo):
        combo.setToolTip(RULE_FUNCTIONS[combo.currentData()][1])
        self.rulesChanged.emit()

    def _update_row(self, row):
        combo = self._table.cellWidget(row, 2)
        mode = combo.currentData()
        combo.setToolTip(RULE_MODES[mode][1])
        for column, applicable in ((3, mode in ("regex", "delimiter_column")), (4, mode == "delimiter_column")):
            item = self._table.item(row, column)
            item.setFlags(EDITABLE if applicable else Qt.ItemFlag.NoItemFlags)
            if not applicable:
                item.setText("")

    def _update_columns(self):
        modes = {self._table.cellWidget(row, 2).currentData() for row in range(self._table.rowCount())}
        self._table.setColumnHidden(3, not modes.intersection(("regex", "delimiter_column")))
        self._table.setColumnHidden(4, "delimiter_column" not in modes)
