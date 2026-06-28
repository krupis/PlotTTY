"""Incremental bytes-to-lines decoder."""

from __future__ import annotations


class LineDecoder:
    """Decode incoming byte chunks into complete text lines."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
        self._buffer = ""

# The feed method takes incoming bytes, decodes them, and extracts complete lines. 
# It handles both \n and \r as line terminators and manages cases where lines may be split across multiple chunks.   
    def feed(self, data: bytes) -> list[str]:
        if not data:
            return []

        # Accumulate text until we see a newline/carriage return.
        text = data.decode(self.encoding, errors="replace")
        if "\n" not in text and "\r" not in text:
            self._buffer += text
            return []

        self._buffer += text
        lines = []
        while True:
            newline_positions = [
                pos for pos in (self._buffer.find("\n"), self._buffer.find("\r")) if pos >= 0
            ]
            if not newline_positions:
                break

            index = min(newline_positions)
            line = self._buffer[:index]
            self._buffer = self._buffer[index + 1 :]
            if self._buffer.startswith("\n") and self._buffer[:1] != line[-1:]:
                self._buffer = self._buffer[1:]
            lines.append(line)

        return lines

    def flush(self) -> str:
        text = self._buffer
        self._buffer = ""
        return text
