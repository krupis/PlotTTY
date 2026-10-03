"""Inline extraction-rule editor."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QStyle, QTableWidget, QVBoxLayout, QWidget

from ..core.extraction import validate_rules
from ..core.rule_suggestions import suggest_rules
from .rules_table import RulesTable


class _RulesTableWidget(QTableWidget):
    """Prefer just enough space for the rows; scroll when the panel is smaller."""

    def sizeHint(self):
        height = self.horizontalHeader().height() + sum(self.rowHeight(row) for row in range(self.rowCount()))
        height += self.frameWidth() * 2
        if self.horizontalHeader().length() > self.viewport().width():
            height += self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        return QSize(super().sizeHint().width(), height)


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
        self.generate_button = QPushButton("Generate rules")
        layout.addWidget(self.generate_button)
        self.table = _RulesTableWidget()
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.table.setMinimumHeight(76)
        self.rules_table = RulesTable(self.table, self)
        self.rules_table.set_rules(rules)
        self._applied_rules = self.rules_table.rules()
        layout.addWidget(self.table)
        row = QHBoxLayout()
        add = QPushButton("Add")
        remove = QPushButton("Remove")
        add.setToolTip("Add an extraction rule")
        remove.setToolTip("Remove selected rules")
        add.setIcon(QIcon(":/icons/plus.svg"))
        remove.setIcon(QIcon(":/icons/minus.svg"))
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch()
        layout.addLayout(row)
        self.apply_button = QPushButton("Apply rules")
        self.apply_button.setProperty("primary", True)
        self.apply_button.setIcon(QIcon(":/icons/check.svg"))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_rules)
        self.feedback = QLabel("No unapplied changes")
        self.feedback.setObjectName("RuleFeedback")
        self.feedback.setWordWrap(True)
        self.feedback.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.feedback)
        layout.addStretch(1)
        self.rules_table.changed.connect(self._mark_pending)
        self.generate_button.clicked.connect(self.generate_rules)
        add.clicked.connect(self.rules_table.add_rule)
        remove.clicked.connect(self.rules_table.remove_selected_rules)

    def generate_rules(self):
        rules = suggest_rules(self.sample.toPlainText())
        if rules:
            self.rules_table.set_rules(rules)
            if self.apply_button.isEnabled():
                self._set_feedback("Rules generated · Apply to use", "pending")
        else:
            self._set_feedback("Paste a sample containing numeric values to generate rules.", "error")

    def _set_feedback(self, text, state):
        self.feedback.setText(text)
        self.feedback.setProperty("state", state)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def _mark_pending(self):
        pending = self.rules_table.rules() != self._applied_rules
        self.apply_button.setEnabled(pending)
        self.table.updateGeometry()
        self._set_feedback("Unapplied changes" if pending else "No unapplied changes", "pending" if pending else "success")

    def mark_applied(self):
        self._applied_rules = self.rules_table.rules()
        self.apply_button.setEnabled(False)
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
