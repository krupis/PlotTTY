"""Plain Qt table for extraction-rule edits."""
from PySide6.QtCore import QObject, QSignalBlocker, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QColorDialog, QComboBox, QHeaderView, QMenu, QTableWidget, QTableWidgetItem, QToolButton

from ..core.extraction import ExtractionRule
from ..core.series_colors import default_series_color

RULE_METHODS = {
    "named_values": ("Named values", "Extract all name/value pairs, such as Voltage: 3.31."),
    "delimited_values": ("Delimited values", "Extract a number from one zero-based field index."),
    "regex_pattern": ("Regex pattern", "The first capture group must contain the numeric value."),
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
    changed = Signal()

    def __init__(self, table: QTableWidget, parent=None):
        super().__init__(parent)
        self._table = table
        table.setColumnCount(7)
        table.setHorizontalHeaderLabels(["Function", "Label", "Method", "Delimiter", "Field", "", "Show"])
        for column, tooltip in enumerate(COLUMN_TOOLTIPS):
            table.horizontalHeaderItem(column).setToolTip(tooltip)
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch
                                                         if column in (1, 3) else QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().hide()
        table.verticalHeader().setDefaultSectionSize(36)
        table.horizontalHeader().setMinimumSectionSize(32)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(5, 32)
        table.horizontalHeader().moveSection(5, 1)
        table.horizontalHeaderItem(5).setToolTip("Series color; right-click a swatch to restore automatic colors")
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().moveSection(6, 0)
        table.horizontalHeaderItem(6).setToolTip("Show this rule's plots after Apply rules. Hidden series keep collecting data.")
        table.setAlternatingRowColors(True)
        table.setSelectionMode(table.SelectionMode.ExtendedSelection)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.itemChanged.connect(self.changed)
        self._update_columns()

    def set_rules(self, rules):
        blocker = QSignalBlocker(self)
        self._table.setRowCount(0)
        for rule in rules:
            self.add_rule(rule)
        self._update_columns()
        self._update_swatches()
        blocker.unblock()
        self.changed.emit()

    def add_rule(self, rule=None):
        blocker = QSignalBlocker(self)
        rule = rule or ExtractionRule("value", "first_number")
        row = self._table.rowCount()
        self._table.insertRow(row)
        texts = ["", rule.label, "", rule.delimiter.replace("\t", r"\t")
                 if rule.method == "delimited_values" else rule.extra_setting,
                 rule.extra_setting if rule.method == "delimited_values" else ""]
        for column, text in enumerate(texts):
            item = QTableWidgetItem(text)
            item.setToolTip(COLUMN_TOOLTIPS[column])
            self._table.setItem(row, column, item)
        visibility = QTableWidgetItem()
        visibility.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
        visibility.setCheckState(Qt.CheckState.Checked if rule.visible else Qt.CheckState.Unchecked)
        visibility.setToolTip("Show or hide this rule's plots after Apply rules. Hidden series keep collecting data.")
        self._table.setItem(row, 6, visibility)
        self._table.item(row, 1).setData(Qt.ItemDataRole.UserRole, rule.unit)
        swatch = QToolButton()
        swatch.setObjectName("RuleColorButton")
        swatch.setProperty("color", rule.color)
        swatch.setIconSize(QSize(16, 16))
        swatch.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        swatch.clicked.connect(lambda: self._choose_color(swatch))
        swatch.customContextMenuRequested.connect(lambda point: self._color_menu(swatch, point))
        self._table.setCellWidget(row, 5, swatch)
        function = QComboBox()
        for value, (label, help_text) in RULE_FUNCTIONS.items():
            function.addItem(label, value)
            function.setItemData(function.count() - 1, help_text, Qt.ItemDataRole.ToolTipRole)
        function.setCurrentIndex(function.findData("time" if rule.is_time else "plot"))
        self._table.setCellWidget(row, 0, function)
        combo = QComboBox()
        for method, (label, help_text) in RULE_METHODS.items():
            combo.addItem(label, method)
            combo.setItemData(combo.count() - 1, help_text, Qt.ItemDataRole.ToolTipRole)
        combo.setCurrentIndex(combo.findData(rule.method))
        self._table.setCellWidget(row, 2, combo)
        self._update_row(row)
        combo.currentIndexChanged.connect(lambda: self._method_changed(combo))
        function.currentIndexChanged.connect(lambda: self._function_changed(function))
        self._function_changed(function)
        self._update_columns()
        self._update_swatches()
        blocker.unblock()
        self.changed.emit()

    def remove_selected_rules(self):
        blocker = QSignalBlocker(self)
        rows = {index.row() for index in self._table.selectedIndexes()}
        if not rows and self._table.currentRow() >= 0:
            rows.add(self._table.currentRow())
        for row in sorted(rows, reverse=True):
            self._table.removeRow(row)
        self._update_columns()
        self._update_swatches()
        blocker.unblock()
        self.changed.emit()

    def rules(self):
        rules = []
        for row in range(self._table.rowCount()):
            method = self._table.cellWidget(row, 2).currentData()
            text = [self._table.item(row, column).text().strip() for column in (1, 3, 4)]
            rules.append(ExtractionRule(
                label=text[0] or "value", method=method,
                is_time=self._table.cellWidget(row, 0).currentData() == "time",
                extra_setting=text[2] if method == "delimited_values" else text[1] if method == "regex_pattern" else "",
                delimiter=text[1].replace(r"\t", "\t") if method == "delimited_values" else ",",
                unit=self._table.item(row, 1).data(Qt.ItemDataRole.UserRole) or "",
                color=self._table.cellWidget(row, 5).property("color") or "",
                visible=self._table.item(row, 6).checkState() == Qt.CheckState.Checked,
            ))
        return rules

    def _method_changed(self, combo):
        blocker = QSignalBlocker(self)
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 2) is combo:
                # Settings belong to a method; start with its defaults when switching.
                self._table.item(row, 3).setText("," if combo.currentData() == "delimited_values" else "")
                self._table.item(row, 4).setText("0" if combo.currentData() == "delimited_values" else "")
                self._update_row(row)
                break
        self._update_columns()
        self._update_swatches()
        blocker.unblock()
        self.changed.emit()

    def _function_changed(self, combo):
        combo.setToolTip(RULE_FUNCTIONS[combo.currentData()][1])
        for row in range(self._table.rowCount()):
            if self._table.cellWidget(row, 0) is combo:
                item = self._table.item(row, 6)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable
                              if combo.currentData() == "plot" else Qt.ItemFlag.NoItemFlags)
                break
        self._update_swatches()
        self.changed.emit()

    def _choose_color(self, swatch):
        color = QColorDialog.getColor(QColor(swatch.property("displayColor")), self._table, "Choose series color")
        if color.isValid():
            swatch.setProperty("color", color.name())
            self._update_swatches()
            self.changed.emit()

    def _color_menu(self, swatch, point):
        menu = QMenu(self._table)
        automatic = menu.addAction("Automatic color")
        if menu.exec(swatch.mapToGlobal(point)) == automatic:
            swatch.setProperty("color", "")
            self._update_swatches()
            self.changed.emit()
        menu.deleteLater()

    def _update_swatches(self):
        index = 0
        for row in range(self._table.rowCount()):
            swatch = self._table.cellWidget(row, 5)
            function = self._table.cellWidget(row, 0)
            if swatch is None or function is None:
                continue
            plotted = function.currentData() == "plot"
            swatch.setVisible(plotted)
            if not plotted:
                continue
            color = swatch.property("color") or default_series_color(index)
            swatch.setProperty("displayColor", color)
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(2, 2, 12, 12)
            painter.end()
            swatch.setIcon(QIcon(pixmap))
            label = self._table.item(row, 1).text()
            swatch.setAccessibleName(f"Color for {label}")
            method = self._table.cellWidget(row, 2)
            hint = "Choose a color for all named series extracted by this rule." if method and method.currentData() == "named_values" else f"Choose color for {label}."
            swatch.setToolTip(hint + " Right-click to restore automatic colors.")
            index += 1

    def _update_row(self, row):
        combo = self._table.cellWidget(row, 2)
        method = combo.currentData()
        combo.setToolTip(RULE_METHODS[method][1])
        for column, applicable in ((3, method in ("regex_pattern", "delimited_values")), (4, method == "delimited_values")):
            item = self._table.item(row, column)
            item.setFlags(EDITABLE if applicable else Qt.ItemFlag.NoItemFlags)
            if not applicable:
                item.setText("")

    def _update_columns(self):
        methods = {self._table.cellWidget(row, 2).currentData() for row in range(self._table.rowCount())}
        self._table.horizontalHeaderItem(3).setText(
            "Pattern / delim." if {"regex_pattern", "delimited_values"}.issubset(methods)
            else "Pattern" if "regex_pattern" in methods else "Delimiter"
        )
        self._table.setColumnHidden(3, not methods.intersection(("regex_pattern", "delimited_values")))
        self._table.setColumnHidden(4, "delimited_values" not in methods)
