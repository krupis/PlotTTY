"""Inline extraction-rule editor."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTableWidget, QVBoxLayout, QWidget

from ..core.extraction import validate_rules
from ..core.rule_suggestions import suggest_rules
from .rules_table import RulesTable


class RulesEditor(QWidget):
    """Draft extraction rules, committed explicitly with visible feedback."""

    rulesApplied = Signal(list)

    def __init__(self, rules, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.sample = QPlainTextEdit()
        self.sample.setObjectName("SampleOutput")
        self.sample.setAccessibleName("Sample output")
        self.sample.setPlaceholderText("Paste sample output to generate rules")
        self.sample.setFixedHeight(self.fontMetrics().lineSpacing() * 3 + 16)
        layout.addWidget(self.sample)
        generate = QPushButton("Generate rules")
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(generate)
        layout.addLayout(row)
        heading = QLabel("Rules")
        heading.setObjectName("SectionHeading")
        layout.addWidget(heading)
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
        self.apply_button = QPushButton("Apply rules")
        self.apply_button.setProperty("primary", True)
        self.apply_button.clicked.connect(self.apply_rules)
        self.feedback = QLabel("No unapplied changes")
        self.feedback.setObjectName("RuleFeedback")
        self.feedback.setWordWrap(True)
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        row = QHBoxLayout()
        row.addWidget(self.apply_button)
        row.addWidget(self.feedback, 1)
        layout.addLayout(row)
        self.rules_table.changed.connect(self._mark_pending)
        generate.clicked.connect(self.generate_rules)
        add.clicked.connect(self.rules_table.add_rule)
        remove.clicked.connect(self.rules_table.remove_selected_rules)

    def generate_rules(self):
        rules = suggest_rules(self.sample.toPlainText())
        if rules:
            self.rules_table.set_rules(rules)
            self._set_feedback("Rules generated · Apply to use", "pending")
        else:
            self._set_feedback("Paste a sample containing numeric values to generate rules.", "error")

    def _set_feedback(self, text, state):
        self.feedback.setText(text)
        self.feedback.setProperty("state", state)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def _mark_pending(self):
        self._set_feedback("Unapplied changes", "pending")

    def mark_applied(self):
        self._set_feedback("Rules applied", "success")

    def apply_rules(self):
        rules = self.rules_table.rules()
        try:
            validate_rules(rules)
        except ValueError as exc:
            self._set_feedback(str(exc), "error")
            return False
        self.rulesApplied.emit(rules)
        self.mark_applied()
        return True
