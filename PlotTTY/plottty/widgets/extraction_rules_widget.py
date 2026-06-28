"""Guided setup and advanced editing for extraction rules."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QPushButton,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from plottty.core.extraction import ExtractionEngine, default_rules
from plottty.core.models import ExtractionRule
from plottty.core.rule_suggestions import RuleSuggestion, suggest_rules_from_samples


class ExtractionRulesWidget(QWidget):
    rulesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggestions: list[RuleSuggestion] = []

        self.tabs = QTabWidget()
        self.setup_tab = QWidget()
        self.advanced_tab = QWidget()

        self.sample_editor = QTextEdit()
        self.sample_editor.setPlaceholderText(
            "Paste a few lines from your device, for example:\n"
            "temp=23.4 humidity=51\n"
            "temp=23.6 humidity=52"
        )
        self.sample_editor.setMinimumHeight(96)

        self.detect_button = QPushButton("Detect Values")
        self.apply_button = QPushButton("Use Selected Values")
        self.apply_button.setEnabled(False)
        self.setup_status = QLabel("Paste sample lines, then detect the values to capture.")
        self.setup_status.setWordWrap(True)

        self.suggestions_table = QTableWidget(0, 4)
        self.suggestions_table.setHorizontalHeaderLabels(["Plot", "Name", "Example", "Found by"])
        self.suggestions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.suggestions_table.verticalHeader().setVisible(False)
        self.suggestions_table.verticalHeader().setDefaultSectionSize(30)
        self.suggestions_table.setAlternatingRowColors(True)
        self.suggestions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(["Line", "Value", "Number"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.verticalHeader().setDefaultSectionSize(30)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Plot", "Use as X", "Label", "Find method", "Extra setting", "Position"])
        header = self.table.horizontalHeader()
        for column in range(self.table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(56)
        self.table.setColumnWidth(0, 64)
        self.table.setColumnWidth(1, 96)
        self.table.setColumnWidth(2, 240)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(4, 320)
        self.table.setColumnWidth(5, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.add_button = QPushButton("Add Rule")
        self.remove_button = QPushButton("Remove Selected")

        self._build_ui()
        self._connect_signals()
        self.set_rules(default_rules())

    def _build_ui(self) -> None:
        setup_buttons = QHBoxLayout()
        setup_buttons.addWidget(self.detect_button)
        setup_buttons.addWidget(self.apply_button)
        setup_buttons.addStretch(1)

        setup_layout = QVBoxLayout(self.setup_tab)
        setup_layout.addWidget(QLabel("Sample device output"))
        setup_layout.addWidget(self.sample_editor)
        setup_layout.addLayout(setup_buttons)
        setup_layout.addWidget(self.setup_status)
        setup_layout.addWidget(self.suggestions_table)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.addWidget(self.preview_table)
        setup_layout.addWidget(preview_group)

        buttons = QHBoxLayout()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)

        advanced_layout = QVBoxLayout(self.advanced_tab)
        advanced_layout.addWidget(QLabel("Edit rules directly when setup does not detect the value you need."))
        advanced_layout.addLayout(buttons)
        advanced_layout.addWidget(self.table)

        self.tabs.addTab(self.setup_tab, "Simple Setup")
        self.tabs.addTab(self.advanced_tab, "Advanced Rules")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

    def _connect_signals(self) -> None:
        self.detect_button.clicked.connect(self.detect_values)
        self.apply_button.clicked.connect(self.apply_selected_suggestions)
        self.suggestions_table.itemChanged.connect(lambda _item: self._refresh_preview())
        self.add_button.clicked.connect(self.add_empty_rule)
        self.remove_button.clicked.connect(self.remove_selected_rule)
        self.table.itemChanged.connect(self._table_item_changed)

    def rules(self) -> list[ExtractionRule]:
        rules = []
        for row in range(self.table.rowCount()):
            enabled_widget = self.table.cellWidget(row, 0)
            sample_counter_widget = self.table.cellWidget(row, 1)
            mode_widget = self.table.cellWidget(row, 3)
            if enabled_widget is None or mode_widget is None:
                continue
            mode = mode_widget.currentData()
            if mode is None:
                continue
            rules.append(
                ExtractionRule(
                    enabled=enabled_widget.isChecked(),
                    label=self._text(row, 2) or "Value",
                    mode=mode,
                    sample_counter=isinstance(sample_counter_widget, QCheckBox)
                    and sample_counter_widget.isChecked(),
                    extra_setting=self._rule_extra_setting(mode, self._text(row, 4), self._text(row, 5)),
                    delimiter=self._rule_delimiter(mode, self._text(row, 4)),
                )
            )
        return rules

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for rule in rules:
            self._append_rule(rule)
        self.table.blockSignals(False)
        self.rulesChanged.emit()

    def detect_values(self) -> None:
        self._suggestions = suggest_rules_from_samples(self.sample_editor.toPlainText())
        self._populate_suggestions()
        self.apply_button.setEnabled(bool(self._suggestions))
        if self._suggestions:
            self.setup_status.setText("Select the values to capture, then use them as rules.")
        else:
            self.setup_status.setText("No numeric values were found. Paste one or more real device lines and try again.")
        self._refresh_preview()

    def apply_selected_suggestions(self) -> None:
        selected_rules = [suggestion.rule for row, suggestion in enumerate(self._suggestions) if self._suggestion_enabled(row)]
        if not selected_rules:
            self.setup_status.setText("Select at least one value before applying rules.")
            return
        self.set_rules(selected_rules)
        self.setup_status.setText("Rules updated. You can keep using setup or fine-tune them in Advanced Rules.")

    def add_empty_rule(self) -> None:
        self.table.blockSignals(True)
        self._append_rule(ExtractionRule(label="New Value", mode="regex", enabled=True))
        self.table.blockSignals(False)
        self.rulesChanged.emit()

    def remove_selected_rule(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        if rows:
            self.rulesChanged.emit()

    def _populate_suggestions(self) -> None:
        self.suggestions_table.blockSignals(True)
        self.suggestions_table.setRowCount(0)
        for suggestion in self._suggestions:
            row = self.suggestions_table.rowCount()
            self.suggestions_table.insertRow(row)

            enabled = QTableWidgetItem()
            enabled.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            enabled.setCheckState(Qt.CheckState.Checked)
            self.suggestions_table.setItem(row, 0, enabled)

            self._set_readonly_item(self.suggestions_table, row, 1, suggestion.label)
            self._set_readonly_item(self.suggestions_table, row, 2, suggestion.example_value)
            self._set_readonly_item(self.suggestions_table, row, 3, suggestion.how_found)
        self.suggestions_table.blockSignals(False)

    def _refresh_preview(self) -> None:
        selected_rules = [suggestion.rule for row, suggestion in enumerate(self._suggestions) if self._suggestion_enabled(row)]
        lines = [line.strip() for line in self.sample_editor.toPlainText().splitlines() if line.strip()]
        engine = ExtractionEngine(selected_rules)

        self.preview_table.setRowCount(0)
        for line in lines:
            for value in engine.extract(line, timestamp=0.0):
                row = self.preview_table.rowCount()
                self.preview_table.insertRow(row)
                self._set_readonly_item(self.preview_table, row, 0, line)
                self._set_readonly_item(self.preview_table, row, 1, value.label)
                self._set_readonly_item(self.preview_table, row, 2, f"{value.value:g}{value.unit}")

    def _append_rule(self, rule: ExtractionRule) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled = QCheckBox()
        enabled.setChecked(rule.enabled)
        enabled.setToolTip("Plot this extracted value.")
        enabled.stateChanged.connect(lambda _state: self.rulesChanged.emit())
        self.table.setCellWidget(row, 0, enabled)

        sample_counter = QCheckBox("Use as X")
        sample_counter.setChecked(rule.sample_counter)
        sample_counter.setToolTip("Use this rule's value as the plot X axis / sample counter.")
        sample_counter.stateChanged.connect(lambda _state, checkbox=sample_counter: self._sample_counter_changed(checkbox))
        self.table.setCellWidget(row, 1, sample_counter)

        mode = QComboBox()
        mode.addItem("Named values", "auto_key_value")
        mode.addItem("Delimited values", "delimiter_column")
        mode.addItem("Regex pattern", "regex")
        mode.addItem("First number", "first_number")
        mode.setMinimumWidth(180)
        mode.setMinimumContentsLength(18)
        mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        mode.setMaxVisibleItems(8)
        mode_view = QListView()
        mode_view.setMinimumWidth(190)
        mode_view.setMinimumHeight(120)
        mode_view.setUniformItemSizes(True)
        mode.setView(mode_view)
        index = mode.findData(rule.mode)
        mode.setCurrentIndex(max(index, 0))
        mode.currentIndexChanged.connect(lambda _index, combo=mode: self._mode_changed(combo))
        self.table.setCellWidget(row, 3, mode)

        self._set_editable_item(row, 2, rule.label)
        self._set_extra_item(row, rule.mode, self._display_extra(rule))
        self._set_position_item(row, rule.mode, self._display_position(rule))

    def _suggestion_enabled(self, row: int) -> bool:
        item = self.suggestions_table.item(row, 0)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def _text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _set_editable_item(self, row: int, column: int, value: str | None) -> None:
        item = QTableWidgetItem(value or "")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, column, item)

    def _set_readonly_item(self, table: QTableWidget, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, column, item)

    def _table_item_changed(self, item: QTableWidgetItem) -> None:
        self.rulesChanged.emit()

    def _mode_changed(self, mode: QComboBox) -> None:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 3) is mode:
                self._set_extra_item(row, mode.currentData(), "")
                self._set_position_item(row, mode.currentData(), "")
                break
        self.rulesChanged.emit()

    def _sample_counter_changed(self, changed_checkbox: QCheckBox) -> None:
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 1)
            if isinstance(checkbox, QCheckBox) and checkbox is not changed_checkbox:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
        self.rulesChanged.emit()

    def _display_extra(self, rule: ExtractionRule) -> str:
        if rule.mode in {"auto_key_value", "first_number"}:
            return ""
        if rule.mode == "delimiter_column":
            return self._display_delimiter(rule.delimiter)
        return rule.extra_setting

    def _display_position(self, rule: ExtractionRule) -> str:
        if rule.mode != "delimiter_column":
            return ""
        try:
            return str(int(rule.extra_setting) + 1)
        except ValueError:
            return rule.extra_setting

    def _rule_extra_setting(self, mode: str, extra: str, position_text: str) -> str:
        if mode in {"auto_key_value", "first_number"}:
            return ""
        if mode != "delimiter_column":
            return extra
        try:
            position = int(position_text)
        except ValueError:
            return position_text
        return str(position - 1)

    def _rule_delimiter(self, mode: str, text: str) -> str:
        if mode != "delimiter_column":
            return ","
        return self._rule_delimiter_text(text)

    def _set_extra_item(self, row: int, mode: str, value: str) -> None:
        if mode in {"auto_key_value", "first_number"}:
            item = QTableWidgetItem("Not needed")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        else:
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            if mode == "regex":
                item.setToolTip("Example: temp=([0-9.]+)")
            elif mode == "delimiter_column":
                item.setToolTip(r"Enter the delimiter, for example , or ; or \t.")
        self.table.setItem(row, 4, item)

    def _set_position_item(self, row: int, mode: str, value: str) -> None:
        if mode != "delimiter_column":
            item = QTableWidgetItem("Not needed")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        else:
            item = QTableWidgetItem(value or "1")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            item.setToolTip("Use 1 for the first value, 2 for the second value, and so on.")
        self.table.setItem(row, 5, item)

    def _display_delimiter(self, delimiter: str) -> str:
        if delimiter == "\t":
            return r"\t"
        return delimiter

    def _rule_delimiter_text(self, delimiter: str) -> str:
        return delimiter.replace(r"\t", "\t")
