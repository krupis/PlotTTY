"""Isolated extraction-rule drafts with explicit commit semantics."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QTableWidget, QVBoxLayout)

from ..core.rule_suggestions import suggest_rules
from .rules_table import RulesTable
from ..core.models import validate_rules


class RulesDialog(QDialog):
    rulesApplied = Signal(list)

    def __init__(self, rules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit extraction rules")
        self.setModal(True)
        self.resize(900, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste sample device output to generate rules, or edit the table below."))
        self.sample = QPlainTextEdit()
        self.sample.setPlaceholderText("Voltage: 3.31 V  Current: 0.14 A")
        self.sample.setFixedHeight(self.fontMetrics().lineSpacing() * 5 + 16)
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
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(self.buttons)
        generate.clicked.connect(self.generate_rules)
        add.clicked.connect(lambda: self.rules_table.add_rule())
        remove.clicked.connect(self.rules_table.remove_selected_rules)
        self.buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply_rules)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

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

    def accept(self):
        if self.apply_rules():
            super().accept()
