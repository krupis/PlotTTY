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
        self.apply_button.setToolTip("Rules are up to date")
        self.apply_button.clicked.connect(self.apply_rules)
        self.error_label = QLabel()
        self.error_label.setObjectName("ValidationError")
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.hide()
        layout.addStretch(1)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.error_label)
        self.rules_table.changed.connect(self._mark_pending)
        self.generate_button.clicked.connect(self.generate_rules)
        add.clicked.connect(self.rules_table.add_rule)
        remove.clicked.connect(self.rules_table.remove_selected_rules)

    def generate_rules(self):
        rules = suggest_rules(self.sample.toPlainText())
        if rules:
            self.rules_table.set_rules(rules)
        else:
            self._show_error("Paste a sample containing numeric values to generate rules.")

    def _show_error(self, text):
        self.error_label.setText(text)
        self.error_label.show()

    def _mark_pending(self):
        pending = self.rules_table.rules() != self._applied_rules
        self.apply_button.setEnabled(pending)
        self.apply_button.setToolTip("Apply unapplied changes" if pending else "Rules are up to date")
        self.table.updateGeometry()
        self.error_label.hide()

    def mark_applied(self):
        self._applied_rules = self.rules_table.rules()
        self.apply_button.setEnabled(False)
        self.apply_button.setToolTip("Rules are up to date")
        self.error_label.hide()

    def apply_rules(self):
        rules = self.rules_table.rules()
        try:
            validate_rules(rules)
        except ValueError as exc:
            self._show_error(str(exc))
            return False
        self.rulesApplied.emit(rules)
        self.mark_applied()
        return True
