"""Small modal loading dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout


class LoadingDialog(QDialog):
    cancel_requested = Signal()

    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedSize(260, 150)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)

        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.progress)
        layout.addWidget(self.message_label)
        layout.addWidget(self.cancel_button)
        layout.addStretch()

    def start(self) -> None:
        self.show()

    def set_message(self, message: str) -> None:
        self.message_label.setText(message)

    def reject(self) -> None:
        self.cancel_button.setEnabled(False)
        self.set_message("Cancelling...")
        self.cancel_requested.emit()
