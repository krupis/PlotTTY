"""Small modal loading dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QProgressBar, QVBoxLayout


class LoadingDialog(QDialog):
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

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.progress)
        layout.addWidget(self.message_label)
        layout.addStretch()

    def start(self) -> None:
        self.show()
        QApplication.processEvents()

    def set_message(self, message: str) -> None:
        self.message_label.setText(message)
        QApplication.processEvents()
