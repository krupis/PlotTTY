"""Connection text logging."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TextIO
from uuid import uuid4


def create_log_path(log_dir: Path, connection: str, suffix: str) -> Path:
    """Create the log directory and sanitize the connection description."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in connection)
    return log_dir / f"{name}_{timestamp}_{uuid4().hex[:8]}_{suffix}"


class SerialSessionLog:
    def __init__(self, log_dir: Path | str = "logs"):
        self.log_dir = Path(log_dir)
        self.path: Path | None = None
        self._file: TextIO | None = None

    def start(self, connection: str) -> Path:
        self.close()
        self.path = create_log_path(self.log_dir, connection, "console.log")
        self._file = self.path.open("x", encoding="utf-8", newline="\n")
        return self.path

    def close(self) -> None:
        if self._file is None:
            return

        file, self._file = self._file, None
        file.close()

    def flush(self) -> None:
        if self._file is not None:
            self._file.flush()

    def write_status(self, message: str) -> None:
        self._write_event("STATUS", message)

    def write_sent(self, command: str) -> None:
        self._write_event("TX", command)

    def write_received(self, data: bytes, encoding: str) -> None:
        if self._file is None or not data:
            return

        text = data.decode(encoding, errors="replace")
        self._write_event("RX", text)

    def _write_event(self, event_type: str, text: str) -> None:
        if self._file is None:
            return

        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        timestamp = datetime.now().isoformat(timespec="milliseconds")
        for line in normalized_text.splitlines() or [""]:
            self._file.write(f"[{timestamp}] {event_type} {line}\n")
