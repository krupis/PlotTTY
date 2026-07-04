"""Incremental bytes-to-lines decoder."""

from __future__ import annotations


class LineDecoder:
    """Decode incoming byte chunks into complete text lines."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
        self._buffer = ""

    def feed(self, data: bytes) -> list[str]:
        if not data:
            return []

        self._buffer += data.decode(self.encoding, errors="replace")
        lines = []

        while True:
            newline_indexes = [
                index for index in (self._buffer.find("\n"), self._buffer.find("\r")) if index >= 0
            ]
            if not newline_indexes:
                return lines

            index = min(newline_indexes)
            line = self._buffer[:index]
            self._buffer = self._buffer[index + 1 :]
            if self._buffer.startswith(("\n", "\r")):
                self._buffer = self._buffer[1:]
            lines.append(line)

    def flush(self) -> str:
        text = self._buffer
        self._buffer = ""
        return text
