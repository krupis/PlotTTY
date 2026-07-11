"""Serial session logging."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class SerialLogEvent:
    timestamp: str
    event_type: str
    text: str


class SerialSessionLog:
    def __init__(self, log_dir: Path | str = "logs"):
        self.log_dir = Path(log_dir)
        self.path: Path | None = None
        self._file: TextIO | None = None

    @property
    def is_open(self) -> bool:
        return self._file is not None

    def start(self, port: str, baudrate: int) -> Path:
        self.close()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_port = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in port)
        self.path = self.log_dir / f"serial_{safe_port}_{baudrate}_{timestamp}.log"
        self._file = self.path.open("w", encoding="utf-8", newline="\n")
        return self.path

    def close(self) -> None:
        if self._file is None:
            return

        self._file.close()
        self._file = None

    def write_status(self, message: str) -> None:
        self._write_text(message)

    def write_sent(self, command: str) -> None:
        self._write_text(command)

    def write_received(self, data: bytes, encoding: str) -> None:
        if self._file is None or not data:
            return

        text = data.decode(encoding, errors="replace")
        self._write_text(text)

    def _write_text(self, text: str) -> None:
        if self._file is None:
            return

        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        self._file.write(normalized_text)
        if not normalized_text.endswith("\n"):
            self._file.write("\n")
        self._file.flush()


def parse_serial_log(text: str) -> list[SerialLogEvent]:
    return [
        SerialLogEvent("", _plain_log_event_type(line), line)
        for line in text.splitlines(keepends=True)
    ]


def _plain_log_event_type(line: str) -> str:
    stripped_line = line.strip()
    if stripped_line.startswith("[connected") or stripped_line.startswith("[disconnected"):
        return "STATUS"
    return "RX"
