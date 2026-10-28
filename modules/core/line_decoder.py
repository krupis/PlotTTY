"""Incremental text decoding and line buffering."""

from __future__ import annotations

from codecs import getincrementaldecoder


class LineDecoder:
    """Decode incoming bytes and collect complete lines across chunks."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
        self._decoder = getincrementaldecoder(encoding)(errors="replace")
        self._partial_line = ""
        self._skip_lf = False

    def decode(self, data: bytes) -> str:
        """Decode new bytes and normalize line endings without waiting for a full line."""
        if not data:
            return ""

        text = self._decoder.decode(data)
        if not text:
            return ""

        # A previous chunk's CR already ended a line; consume its matching LF.
        if self._skip_lf and text.startswith("\n"):
            text = text[1:]
        self._skip_lf = text.endswith("\r")

        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        return normalized_text

    def split_lines(self, text: str) -> list[str]:
        """Return complete lines, keeping the unfinished tail for the next call."""
        if not text:
            return []

        combined_text = self._partial_line + text
        complete_lines = combined_text.split("\n")
        self._partial_line = complete_lines.pop()
        return complete_lines
