"""Isolated extraction-rule drafts with explicit commit semantics."""
from dataclasses import replace
import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QTableWidget, QVBoxLayout)

from ..core.rule_suggestions import suggest_rules
from .rules_table import COLUMN_TOOLTIPS, RulesTable


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
        self.table.setHorizontalHeaderLabels(["Enable", "X reference", "Label", "Find method", "Pattern / delimiter", "Field index"])
        for column, tooltip in enumerate(COLUMN_TOOLTIPS):
            self.table.horizontalHeaderItem(column).setToolTip(tooltip)
        self.rules_table.set_rules([replace(rule) for rule in rules])
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
        errors = []
        for row, rule in enumerate(rules, 1):
            try:
                if rule.mode == "regex" and re.compile(rule.extra_setting).groups < 1:
                    raise ValueError("Regex must contain a capture group for the numeric value.")
                if rule.mode == "delimiter_column" and (not rule.extra_setting.isdecimal()):
                    raise ValueError("Field index must be a nonnegative integer.")
            except (ValueError, re.error) as exc:
                errors.append(f"Row {row}: {exc}")
        self.error.setText("\n".join(errors))
        if errors:
            return False
        self.rulesApplied.emit([replace(rule) for rule in rules])
        return True

    def accept(self):
        if self.apply_rules():
            super().accept()
