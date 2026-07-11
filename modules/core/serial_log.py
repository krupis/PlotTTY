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
        self._file.flush()


def parse_serial_log(text: str) -> list[SerialLogEvent]:
    events = []
    for line in text.splitlines():
        event = _parse_timestamped_line(line)
        if event is not None:
            events.append(event)
    return events


def _parse_timestamped_line(line: str) -> SerialLogEvent | None:
    if not line.startswith("["):
        return None

    timestamp_end = line.find("]")
    if timestamp_end <= 1:
        return None

    timestamp = line[1:timestamp_end]
    rest = line[timestamp_end + 1 :].lstrip()
    for event_type in ("STATUS", "TX", "RX"):
        if rest == event_type:
            return SerialLogEvent(timestamp, event_type, "\n")
        if rest.startswith(f"{event_type} "):
            return SerialLogEvent(timestamp, event_type, f"{rest[len(event_type) + 1:]}\n")
    return None
