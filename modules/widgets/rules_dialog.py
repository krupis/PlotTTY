"""Reusable extraction-rule editor with an optional legacy dialog host."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QTableWidget, QVBoxLayout,
                             QWidget)

from ..core.rule_suggestions import suggest_rules
from .rules_table import RulesTable
from ..core.extraction import validate_rules


class RulesEditor(QWidget):
    """Editable extraction rules that can live in a sidebar or a dialog."""
    rulesApplied = Signal(list)

    def __init__(self, rules, parent=None, *, show_apply=True):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Paste sample device output to generate rules, or edit the table below."))
        self.sample = QPlainTextEdit()
        self.sample.setPlaceholderText("Voltage: 3.31 V  Current: 0.14 A")
        self.sample.setFixedHeight(self.fontMetrics().lineSpacing() * 3 + 16)
        layout.addWidget(self.sample)
        generate = QPushButton("Generate rules")
        row = QHBoxLayout()
        row.addWidget(generate)
        row.addStretch()
        layout.addLayout(row)
        self.table = QTableWidget()
        self.rules_table = RulesTable(self.table, self)
        self.rules_table.set_rules(rules)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        add = QPushButton("Add rule")
        remove = QPushButton("Remove selected")
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)
        self.error = QLabel()
        self.error.setObjectName("ValidationError")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        generate.clicked.connect(self.generate_rules)
        add.clicked.connect(lambda: self.rules_table.add_rule())
        remove.clicked.connect(self.rules_table.remove_selected_rules)
        self.apply_button = None
        if show_apply:
            self.apply_button = QPushButton("Apply rules")
            self.apply_button.clicked.connect(self.apply_rules)
            layout.addWidget(self.apply_button)

    def generate_rules(self):
        rules = suggest_rules(self.sample.toPlainText())
        if rules:
            self.rules_table.set_rules(rules)
            self.error.clear()
        else:
            self.error.setText("No numeric values found in sample output.")

    def apply_rules(self):
        rules = self.rules_table.rules()
        try:
            validate_rules(rules)
        except ValueError as exc:
            self.error.setText(str(exc))
            return False
        self.error.clear()
        self.rulesApplied.emit(rules)
        return True


class RulesDialog(QDialog):
    """Legacy modal host kept for callers that explicitly need a dialog."""

    rulesApplied = Signal(list)

    def __init__(self, rules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit extraction rules")
        self.setModal(True)
        self.resize(900, 560)
        layout = QVBoxLayout(self)
        self.editor = RulesEditor(rules, self, show_apply=False)
        layout.addWidget(self.editor)
        # Keep these attributes for existing integrations using the dialog API.
        self.sample = self.editor.sample
        self.table = self.editor.table
        self.rules_table = self.editor.rules_table
        self.error = self.editor.error
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.buttons)
        self.editor.rulesApplied.connect(self.rulesApplied)
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_rules)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def generate_rules(self):
        self.editor.generate_rules()

    def apply_rules(self):
        return self.editor.apply_rules()

    def accept(self):
        if self.apply_rules():
            super().accept()
