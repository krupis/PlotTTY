"""Command entry, history, and quick-command controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget


class CommandPanel(QWidget):
    sendRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("Command")
        self.history_combo = QComboBox()
        self.history_combo.setMinimumWidth(180)
        self.history_combo.addItem("History")
        self.send_button = QPushButton("Send")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.command_edit, stretch=1)
        layout.addWidget(self.history_combo)
        layout.addWidget(self.send_button)

        self.command_edit.returnPressed.connect(self._emit_current)
        self.send_button.clicked.connect(self._emit_current)
        self.history_combo.activated.connect(self._use_history)

    def add_command(self, command: str) -> None:
        command = command.strip()
        if not command or self.history_combo.findText(command) >= 0:
            return
        self.history_combo.addItem(command)

    def commands(self) -> list[str]:
        return [self.history_combo.itemText(index) for index in range(1, self.history_combo.count())]

    def set_commands(self, commands: list[str]) -> None:
        self.history_combo.clear()
        self.history_combo.addItem("History")
        for command in commands:
            self.add_command(command)

    def _emit_current(self) -> None:
        command = self.command_edit.text().strip()
        if command:
            self.add_command(command)
            self.sendRequested.emit(command)

    def _use_history(self, index: int) -> None:
        if index > 0:
            self.command_edit.setText(self.history_combo.itemText(index))
