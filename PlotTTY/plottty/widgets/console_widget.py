"""Line-oriented serial console view."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget


# Refresh console every 50ms to batch updates and avoid UI freezes when a large amount of data is received at once.
CONSOLE_FLUSH_INTERVAL_MS = 50
# Keep a reasonable amount of history in the console to prevent memory issues. The QPlainTextEdit will automatically discard old lines when the limit is exceeded.
VISIBLE_LINE_HISTORY = 2_000


class ConsoleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SerialConsole")
        self._pending_segments: list[tuple[str, str]] = []

        rx_format = QTextCharFormat()
        rx_format.setForeground(QColor("#111111"))
        tx_format = QTextCharFormat()
        tx_format.setForeground(QColor("#0f766e"))
        tx_format.setFontWeight(600)
        self._formats = {
            "rx": rx_format,
            "tx": tx_format,
        }

        self.text_view = QPlainTextEdit(self)
        self.text_view.setObjectName("SerialConsoleText")
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text_view.document().setMaximumBlockCount(VISIBLE_LINE_HISTORY)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_view)

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(CONSOLE_FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self.flush)

    def append(self, data: bytes | str, source: str = "rx", encoding: str = "utf-8") -> None:
        if not data:
            return

        if isinstance(data, bytes):
            text = data.decode(encoding, errors="replace")
        else:
            text = data
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self._pending_segments.append((text, source))
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def clear(self) -> None:
        self._pending_segments.clear()
        self.text_view.clear()

    def flush(self) -> None:
        if not self._pending_segments:
            self._flush_timer.stop()
            return

        pending_segments = self._pending_segments
        self._pending_segments = []

        cursor = self.text_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for text, source in pending_segments:
            cursor.insertText(text, self._formats.get(source, self._formats["rx"]))
        self.text_view.setTextCursor(cursor)
        self.text_view.ensureCursorVisible()
