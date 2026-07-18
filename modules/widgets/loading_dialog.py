"""Small modal loading dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout


SPINNER_PATH = Path(__file__).resolve().parents[2] / "icons" / "spinner_transparent.gif"


class LoadingDialog(QDialog):
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedSize(260, 150)

        self.spinner_label = QLabel()
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.movie = QMovie(str(SPINNER_PATH), parent=self)
        self.spinner_label.setMovie(self.movie)

        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.spinner_label)
        layout.addWidget(self.message_label)
        layout.addStretch()

    def start(self) -> None:
        self.movie.start()
        self.show()
        QApplication.processEvents()

    def set_message(self, message: str) -> None:
        self.message_label.setText(message)
        QApplication.processEvents()

    def closeEvent(self, event) -> None:
        self.movie.stop()
        super().closeEvent(event)
