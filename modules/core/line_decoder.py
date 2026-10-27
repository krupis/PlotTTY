"""Incremental bytes-to-lines decoder."""

from __future__ import annotations

from codecs import getincrementaldecoder


class LineDecoder:
    """Decode incoming byte chunks into complete text lines."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
        self._decoder = getincrementaldecoder(encoding)(errors="replace")
        self._buffer = ""
        self._skip_lf = False

    def feed(self, data: bytes) -> tuple[str, list[str]]:
        """Return normalized decoded text and complete lines for extraction."""
        if not data:
            return "", []

        text = self._decoder.decode(data)
        if not text:
            return "", []

        # A previous chunk's CR already ended a line; consume its matching LF.
        if self._skip_lf and text.startswith("\n"):
            text = text[1:]
        self._skip_lf = text.endswith("\r")

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = (self._buffer + text).split("\n")
        self._buffer = lines.pop()  # Keep the unfinished line for the next chunk.
        return text, lines
