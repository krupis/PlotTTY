"""Dialog for detecting extraction rules from sample device output."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from ..core.extraction import ExtractionEngine
from ..core.models import ExtractionRule
from ..core.rule_suggestions import RuleSuggestion, suggest_rules_from_samples


class RuleSuggestionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detect Rules")
        self.resize(780, 560)
        self._suggestions: list[RuleSuggestion] = []

        self.sample_editor = QTextEdit()
        self.sample_editor.setPlaceholderText(
            "Paste a few lines from your device, for example:\n"
            "181917,3.323100,22.799999,4.907000,160.472717\n"
            "181918,3.322400,22.950001,4.906077,160.800003"
        )
        self.sample_editor.setMinimumHeight(120)

        self.detect_button = QPushButton("Detect Values")
        self.status_label = QLabel("Paste sample lines, then detect values.")

        self.suggestions_table = QTableWidget(0, 4)
        self.suggestions_table.setHorizontalHeaderLabels(["Plot", "Name", "Example", "Found by"])
        self.suggestions_table.verticalHeader().setVisible(False)
        self.suggestions_table.setAlternatingRowColors(True)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.suggestions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(["Line", "Value", "Number"])
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use Selected Values")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        top_buttons = QHBoxLayout()
        top_buttons.addWidget(self.detect_button)
        top_buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sample device output"))
        layout.addWidget(self.sample_editor)
        layout.addLayout(top_buttons)
        layout.addWidget(self.status_label)
        layout.addWidget(self.suggestions_table)
        layout.addWidget(QLabel("Preview"))
        layout.addWidget(self.preview_table)
        layout.addWidget(self.buttons)

        self.detect_button.clicked.connect(self.detect_values)
        self.suggestions_table.itemChanged.connect(lambda _item: self._refresh_preview())
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def selected_rules(self) -> list[ExtractionRule]:
        return [
            suggestion.rule
            for row, suggestion in enumerate(self._suggestions)
            if self._suggestion_enabled(row)
        ]

    def detect_values(self) -> None:
        self._suggestions = suggest_rules_from_samples(self.sample_editor.toPlainText())
        self._populate_suggestions()
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self._suggestions))
        if self._suggestions:
            self.status_label.setText("Select the values to capture, then use them as rules.")
        else:
            self.status_label.setText("No numeric values were found.")
        self._refresh_preview()

    def _populate_suggestions(self) -> None:
        self.suggestions_table.blockSignals(True)
        self.suggestions_table.setRowCount(0)

        for suggestion in self._suggestions:
            row = self.suggestions_table.rowCount()
            self.suggestions_table.insertRow(row)

            enabled = QTableWidgetItem()
            enabled.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            enabled.setCheckState(Qt.CheckState.Checked)
            self.suggestions_table.setItem(row, 0, enabled)

            _set_readonly_item(self.suggestions_table, row, 1, suggestion.label)
            _set_readonly_item(self.suggestions_table, row, 2, suggestion.example_value)
            _set_readonly_item(self.suggestions_table, row, 3, suggestion.how_found)

        self.suggestions_table.blockSignals(False)

    def _refresh_preview(self) -> None:
        selected_rules = self.selected_rules()
        lines = [line.strip() for line in self.sample_editor.toPlainText().splitlines() if line.strip()]
        engine = ExtractionEngine(selected_rules)

        self.preview_table.setRowCount(0)
        for line in lines:
            for value in engine.extract(line, timestamp=0.0):
                row = self.preview_table.rowCount()
                self.preview_table.insertRow(row)
                _set_readonly_item(self.preview_table, row, 0, line)
                _set_readonly_item(self.preview_table, row, 1, value.label)
                _set_readonly_item(self.preview_table, row, 2, f"{value.value:g}{value.unit}")

    def _suggestion_enabled(self, row: int) -> bool:
        item = self.suggestions_table.item(row, 0)
        return item is not None and item.checkState() == Qt.CheckState.Checked


def _set_readonly_item(table: QTableWidget, row: int, column: int, value: str) -> None:
    item = QTableWidgetItem(value)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    table.setItem(row, column, item)
