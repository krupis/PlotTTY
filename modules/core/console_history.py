"""UTF-8 console history with a sparse line index and background search."""
from array import array
from bisect import bisect_right
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from time import sleep
from PySide6.QtCore import QThread

INDEX_STRIDE = 512


class ConsoleHistory:
    """Keep text on disk; retain only line checkpoints and color changes in RAM."""
    def __init__(self):
        self.file = NamedTemporaryFile(prefix='plottty_console_', suffix='.log', delete=False)
        self.path = Path(self.file.name)
        self._reset_index()

    def _reset_index(self):
        self.count, self.size = 1, 0
        self.offsets = array('Q', [0])
        self.color_offsets, self.colors = array('Q'), array('I')
        self._skip_lf = False

    def append(self, text, color):
        """Append normalized text, indexing the start of every 512th line."""
        if self._skip_lf and text.startswith('\n'):
            text = text[1:]
        self._skip_lf = text.endswith('\r')
        data = text.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        if not data:
            return
        if not self.colors or color != self.colors[-1]:
            self.color_offsets.append(self.size)
            self.colors.append(color)
        self.file.seek(self.size)
        self.file.write(data)
        offset = self.size
        for part in data.split(b'\n')[:-1]:
            offset += len(part) + 1
            self.count += 1
            if (self.count - 1) % INDEX_STRIDE == 0:
                self.offsets.append(offset)
        self.size += len(data)

    def read(self, first, count):
        """Read a line window as consecutive (text, RGB color) segments."""
        self.file.seek(self.offsets[first // INDEX_STRIDE])
        for _ in range(first % INDEX_STRIDE):
            self.file.readline()
        offset = self.file.tell()
        rows = [self.file.readline() for _ in range(min(count, self.count - first))]
        rows[-1] = rows[-1].removesuffix(b'\n')
        data = b''.join(rows)
        segments, cursor = [], 0
        index = max(0, bisect_right(self.color_offsets, offset) - 1)
        while cursor < len(data):
            end = min(len(data), self.color_offsets[index + 1] - offset) if index + 1 < len(self.colors) else len(data)
            segments.append((data[cursor:end].decode('utf-8'), self.colors[index]))
            cursor, index = end, index + 1
        return segments

    def clear(self):
        self.file.seek(0)
        self.file.truncate()
        self._reset_index()

    def close(self):
        if not self.file.closed:
            self.file.close()
            self.path.unlink(missing_ok=True)

    def __del__(self):
        self.close()


class ConsoleSearch(QThread):
    """Count all matches and choose one without retaining a list of every match."""
    def __init__(self, path, size, query, current, backwards, parent):
        super().__init__(parent)
        self.path, self.size, self.query = path, size, query
        self.current, self.backwards = current, backwards
        self.match, self.total, self.error = None, 0, None

    def run(self):
        first = last = selected = None
        pattern = re.compile(re.escape(self.query), re.IGNORECASE)
        try:
            with self.path.open('rb') as file:
                row, remaining, pending = 0, self.size, b''
                while remaining:
                    if self.isInterruptionRequested():
                        return
                    data = file.read(min(65536, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    pending += data
                    # Keep an incomplete UTF-8 line for the next chunk.
                    split = pending.rfind(b'\n') + 1 if remaining else len(pending)
                    text, pending = pending[:split].decode('utf-8'), pending[split:]
                    match_row, previous = row, 0
                    for match in pattern.finditer(text):
                        self.total += 1
                        if not self.backwards and selected is not None:
                            continue
                        match_row += text.count('\n', previous, match.start())
                        line_start = text.rfind('\n', 0, match.start()) + 1
                        location = (match_row, match.start() - line_start)
                        point = (match_row, len(text[line_start:match.start()].encode('utf-16-le')) // 2,
                                 len(match.group().encode('utf-16-le')) // 2, self.total)
                        first, last = first or point, point
                        if self.backwards and location < self.current:
                            selected = point
                        elif not self.backwards and selected is None and location >= self.current:
                            selected = point
                        previous = match.start()
                    row += text.count('\n')
                    # Let GUI painting and serial processing run between blocks.
                    sleep(.002)
            self.match = selected or (last if self.backwards else first)
        except OSError as error:
            self.error = str(error)
