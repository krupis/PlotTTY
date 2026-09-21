"""Serial session logging."""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

from .models import CapturedValue


LOAD_PROGRESS_UPDATE_ROWS = 10_000


def _create_log_path(log_dir: Path, port: str, baudrate: int, suffix: str) -> Path:
    """Create the log directory and build a filename safe for the port name."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_port = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in port)
    return log_dir / f"serial_{safe_port}_{baudrate}_{timestamp}_{suffix}"


class SerialSessionLog:
    def __init__(self, log_dir: Path | str = "logs"):
        self.log_dir = Path(log_dir)
        self.path: Path | None = None
        self._file: TextIO | None = None

    def start(self, port: str, baudrate: int) -> Path:
        self.close()
        self.path = _create_log_path(self.log_dir, port, baudrate, "console.log")
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


class PlotSessionLog:
    def __init__(self, log_dir: Path | str = "logs"):
        self.log_dir = Path(log_dir)
        self.path: Path | None = None
        self._file: TextIO | None = None
        self._writer: csv.writer | None = None

    def start(self, port: str, baudrate: int) -> Path:
        self.close()
        self.path = _create_log_path(self.log_dir, port, baudrate, "plot.csv")
        self._file = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow(("timestamp", "label", "value", "unit", "raw_text"))
        return self.path

    def close(self) -> None:
        if self._file is None:
            return

        self._file.close()
        self._file = None
        self._writer = None

    def write_values(self, values: list[CapturedValue]) -> None:
        if self._writer is None or self._file is None or not values:
            return

        for value in values:
            self._writer.writerow((value.timestamp, value.label, value.value, value.unit, value.raw_text))



def read_plot_csv(
    path: str | Path,
    progress_callback: Callable[[int], None] | None = None,
) -> list[CapturedValue]:
    """Load CSV records, including quoted fields containing embedded newlines."""
    captured_values = []
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as file:
        for row in csv.reader(file):
            captured = _parse_plot_row(row)
            if captured is None:
                continue

            captured_values.append(captured)
            row_count = len(captured_values)
            if progress_callback is not None and row_count % LOAD_PROGRESS_UPDATE_ROWS == 0:
                progress_callback(row_count)
    return captured_values


def _parse_plot_row(row: list[str]) -> CapturedValue | None:
    if not row or row[0] == "timestamp" or len(row) < 3:
        return None

    try:
        timestamp = float(row[0])
        value = float(row[2])
    except ValueError:
        return None

    label = row[1].strip() or "value"
    unit = row[3] if len(row) > 3 else ""
    raw_text = row[4] if len(row) > 4 else ""
    return CapturedValue(timestamp=timestamp, label=label, value=value, unit=unit, raw_text=raw_text)
