"""Inline extraction-rule editor."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTableWidget, QVBoxLayout, QWidget

from ..core.extraction import validate_rules
from ..core.rule_suggestions import suggest_rules
from .rules_table import RulesTable


class RulesEditor(QWidget):
    """Editable extraction rules that commit valid edits immediately."""

    rulesApplied = Signal(list)

    def __init__(self, rules, parent=None):
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
        generate.clicked.connect(self.generate_rules)
        add.clicked.connect(self.rules_table.add_rule)
        remove.clicked.connect(self.rules_table.remove_selected_rules)
        self._syncing_rules = False
        self.table.itemChanged.connect(lambda _item: self._apply_changed_rules())
        self.rules_table.rulesChanged.connect(self._apply_changed_rules)

    def set_rules(self, rules):
        self._syncing_rules = True
        try:
            self.rules_table.set_rules(rules)
        finally:
            self._syncing_rules = False

    def _apply_changed_rules(self):
        if not self._syncing_rules:
            self.apply_rules()

    def generate_rules(self):
        rules = suggest_rules(self.sample.toPlainText())
        if rules:
            self.set_rules(rules)
            self.apply_rules()

    def apply_rules(self):
        rules = self.rules_table.rules()
        try:
            validate_rules(rules)
        except ValueError:
            return False
        self.rulesApplied.emit(rules)
        return True
