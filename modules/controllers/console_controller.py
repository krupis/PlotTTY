"""Display a small window of complete, file-backed console history."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QScrollBar
from ..core.console_history import ConsoleHistory, ConsoleSearch

RECEIVED_TEXT_COLOR = QColor("#ffffff")
SENT_TEXT_COLOR = QColor("#ffd782")
STATUS_TEXT_COLOR = QColor("#a9ccff")
CONSOLE_VIEW_BLOCKS = 512
CONSOLE_FLUSH_INTERVAL_MS = 50


class ConsoleController(QObject):
    searchFinished = Signal(int, int)

    def __init__(self, editor: QPlainTextEdit, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._history = ConsoleHistory()
        self._dirty = False
        self.show_receive_timestamps = False
        self._at_line_start = True
        self._window_first = 0
        self._rendering = False
        self._job = self._request = None
        self._query = ""
        self._editor.setReadOnly(True)
        self._editor.setLineWrapMode(self._editor.LineWrapMode.NoWrap)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setToolTip("Scroll or search the complete session history. Select and copy displayed text.")
        self.scroll_bar = QScrollBar(Qt.Orientation.Vertical, editor)
        editor.setViewportMargins(0, 0, self.scroll_bar.sizeHint().width(), 0)
        self.scroll_bar.valueChanged.connect(self._scrolled)
        editor.verticalScrollBar().valueChanged.connect(self._inner_scrolled)
        editor.viewport().installEventFilter(self)
        editor.installEventFilter(self)
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(CONSOLE_FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self.flush)
        self._flush_timer.start()
        self._update_scrollbar(0)
        self._position_scrollbar()

    def _position_scrollbar(self):
        area = self._editor.viewport().geometry()
        self.scroll_bar.setGeometry(area.right() + 1, area.top(), self.scroll_bar.sizeHint().width(), area.height())

    def _visible_rows(self):
        return max(1, self._editor.viewport().height() // max(1, self._editor.fontMetrics().height()))

    def _update_scrollbar(self, value):
        self._rendering = True
        self.scroll_bar.setPageStep(self._visible_rows())
        self.scroll_bar.setRange(0, max(0, self._history.count - self._visible_rows()))
        self.scroll_bar.setValue(value)
        self.scroll_bar.setVisible(self.scroll_bar.maximum() > 0)
        self._rendering = False

    def _render(self):
        """Seek to the requested lines; only this window becomes a Qt document."""
        top = self.scroll_bar.value()
        capacity = max(CONSOLE_VIEW_BLOCKS, self._visible_rows() + 64)
        start = max(0, min(top - 64, self._history.count - capacity))
        segments = self._history.read(start, capacity)
        self._rendering = True
        self._window_first = start
        self._editor.document().setMaximumBlockCount(capacity)
        self._editor.clear()
        cursor = QTextCursor(self._editor.document())
        text_format = QTextCharFormat()
        for text, color in segments:
            text_format.setForeground(QColor.fromRgb(color))
            cursor.insertText(text, text_format)
        self._editor.verticalScrollBar().setValue(max(0, top - start))
        self._rendering = False

    def _scrolled(self, value):
        if not self._rendering:
            self._render()

    def _inner_scrolled(self, value):
        if not self._rendering:
            self.scroll_bar.setValue(self._window_first + value)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel and event.angleDelta().y():
            steps = round(event.angleDelta().y() / 120 * QApplication.wheelScrollLines())
            self.scroll_bar.setValue(self.scroll_bar.value() - steps)
            return True
        if event.type() == QEvent.Type.Resize and not self._rendering:
            self._position_scrollbar()
            following = self.scroll_bar.value() >= self.scroll_bar.maximum()
            self._update_scrollbar(self._history.count if following else self.scroll_bar.value())
        return super().eventFilter(watched, event)

    def _stop_search(self):
        self._request = None
        if self._job is not None:
            self._job.finished.disconnect(self._search_done)
            self._job.requestInterruption()
            self._job.wait()
            self._job.deleteLater()
            self._job = None

    def clear(self) -> None:
        self._stop_search()
        self._query = ""
        self._dirty = False
        self._history.clear()
        self._at_line_start = True
        self._update_scrollbar(0)
        self._render()
        self.searchFinished.emit(0, 0)

    def find_text(self, text: str, *, backwards: bool = False) -> None:
        """Search a snapshot of the full file without blocking the GUI."""
        self.flush()
        cursor = self._editor.textCursor()
        position = cursor.selectionStart() if backwards else cursor.selectionEnd()
        block = self._editor.document().findBlock(position)
        column = len(block.text().encode("utf-16-le")[:(position - block.position()) * 2].decode("utf-16-le"))
        current = (self._window_first + block.blockNumber(), column) if text == self._query else (0, 0)
        self._query = text
        self._request = (text, current, backwards) if text else None
        if self._job is not None:
            self._job.requestInterruption()
        elif self._request:
            self._start_search()
        if not text:
            self.searchFinished.emit(0, 0)

    def _start_search(self):
        self._history.file.flush()
        self._job = ConsoleSearch(self._history.path, self._history.size, *self._request, self)
        self._request = None
        self._job.finished.connect(self._search_done)
        self._job.start()

    def _search_done(self):
        job = self.sender()
        if self._job is None or job is not self._job:
            return
        self._job = None
        if self._request:
            self._start_search()
        elif not job.isInterruptionRequested():
            if job.match:
                row, column, length, number = job.match
                self._update_scrollbar(max(0, row - self._visible_rows() // 2))
                self._render()
                block = self._editor.document().findBlockByNumber(row - self._window_first)
                cursor = QTextCursor(block)
                cursor.setPosition(block.position() + column)
                cursor.setPosition(cursor.position() + length, QTextCursor.MoveMode.KeepAnchor)
                self._editor.setTextCursor(cursor)
                self._editor.ensureCursorVisible()
            self.searchFinished.emit(job.match[3] if job.match else 0, job.total)
        job.deleteLater()

    @Slot(str, float)
    def append_received(self, text: str, received_at: float) -> None:
        if not text:
            return
        if self.show_receive_timestamps:
            prefix = f"[{received_at:.3f}] "
            # The previous chunk may have left a line unfinished.
            at_line_start = self._at_line_start
            stamped_lines = []
            # Preserve newlines so we can track where each new line begins.
            for line in text.splitlines(keepends=True):
                # Stamp new lines once; continuations keep their existing timestamp.
                if at_line_start:
                    stamped_lines.append(prefix + line)
                else:
                    stamped_lines.append(line)
                # An unfinished final line continues without a prefix in the next chunk.
                at_line_start = line.endswith("\n")
            text = "".join(stamped_lines)
        self.append_text(text, RECEIVED_TEXT_COLOR)

    @Slot(bool)
    def set_receive_timestamps_visible(self, visible: bool) -> None:
        self.show_receive_timestamps = visible

    @Slot(str)
    def append_sent(self, text: str) -> None:
        self.append_text(text, SENT_TEXT_COLOR)

    @Slot(str)
    def append_status(self, text: str) -> None:
        self.append_text(text, STATUS_TEXT_COLOR)

    def append_text(self, text: str, color: QColor | None = None) -> None:
        """Store text immediately; the timer batches only display updates."""
        if text:
            self._history.append(text, (color or RECEIVED_TEXT_COLOR).rgb())
            self._at_line_start = text.endswith(("\n", "\r"))
            self._dirty = True

    @Slot()
    def flush(self) -> None:
        """Refresh the history range and, when following, the visible tail."""
        if not self._dirty:
            return
        following = self.scroll_bar.value() >= self.scroll_bar.maximum() and not self._editor.textCursor().hasSelection()
        top = self.scroll_bar.value()
        self._dirty = False
        self._update_scrollbar(self._history.count if following else top)
        if following:
            self._render()

    @Slot()
    def close(self):
        if self._history.file.closed:
            return
        self._flush_timer.stop()
        self._stop_search()
        self.flush()
        self._history.close()

    def set_display_active(self, active: bool) -> None:
        """Keep storing background traffic; render the latest window on return."""
        if active:
            self._flush_timer.start()
            self.flush()
        else:
            self._flush_timer.stop()
