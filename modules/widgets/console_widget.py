"""Buffered console rendering for serial text."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


RECEIVED_TEXT_COLOR = QColor("#1f8f3a")
SENT_TEXT_COLOR = QColor("#b58900")
STATUS_TEXT_COLOR = QColor("#1f6feb")
MAX_CONSOLE_BLOCKS = 10_000
CONSOLE_FLUSH_INTERVAL_MS = 50


class ConsoleWidget(QObject):
    def __init__(self, editor: QPlainTextEdit, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._pending_text: list[tuple[str, QColor | None]] = []
        self._line_limit_enabled = True

        self._editor.setReadOnly(True)
        self._editor.setLineWrapMode(self._editor.LineWrapMode.NoWrap)
        self.set_line_limit_enabled(self._line_limit_enabled)

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(CONSOLE_FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self.on_flush)
        self._flush_timer.start()

    def clear(self) -> None:
        self._pending_text.clear()
        self._editor.clear()

    def set_line_limit_enabled(self, enabled: bool) -> None:
        self._line_limit_enabled = enabled
        maximum_blocks = MAX_CONSOLE_BLOCKS if enabled else 0
        self._editor.document().setMaximumBlockCount(maximum_blocks)

    @Slot(str)
    def append_received(self, text: str) -> None:
        self.append_text(text, RECEIVED_TEXT_COLOR)

    @Slot(str)
    def append_sent(self, text: str) -> None:
        self.append_text(text, SENT_TEXT_COLOR)

    @Slot(str)
    def append_status(self, text: str) -> None:
        self.append_text(text, STATUS_TEXT_COLOR)

    def append_text(self, text: str, color: QColor | None = None) -> None:
        if not text:
            return

        if self._pending_text and self._pending_text[-1][1] == color:
            previous_text, previous_color = self._pending_text[-1]
            self._pending_text[-1] = (previous_text + text, previous_color)
        else:
            self._pending_text.append((text, color))

    @Slot()
    def on_flush(self) -> None:
        if not self._pending_text:
            return

        pending_text = self._pending_text
        self._pending_text = []

        scroll_bar = self._editor.verticalScrollBar()
        was_at_bottom = scroll_bar.value() >= scroll_bar.maximum()
        previous_scroll_value = scroll_bar.value()

        cursor = QTextCursor(self._editor.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        for text, color in pending_text:
            text_format = QTextCharFormat()
            if color is not None:
                text_format.setForeground(color)
            cursor.insertText(text.replace("\r\n", "\n").replace("\r", "\n"), text_format)
        cursor.endEditBlock()

        if self._line_limit_enabled or was_at_bottom:
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()
        else:
            scroll_bar.setValue(previous_scroll_value)
