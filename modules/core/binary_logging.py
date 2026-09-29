"""Binary recording, streaming reads, and CSV export for PlotTTY captures.

See docs/CAPTURE_FORMAT.md for the on-disk format. No pickle or third-party
codec is used. Numeric values are IEEE-754 doubles, matching CapturedValue.
"""

import csv
import os
import tempfile
from collections.abc import Iterator, Iterable
from pathlib import Path
import struct
from typing import BinaryIO
import zlib

from .extraction import CapturedValue
from .serial_log import create_log_path


MAGIC = b"PLOTTY\x00\x01"
BLOCK_HEADER = struct.Struct("<II")
UINT = struct.Struct("<I")
SAMPLE_HEADER = struct.Struct("<dII")  # timestamp, raw-text bytes, value count
VALUE = struct.Struct("<Id")  # series ID, numeric value
BLOCK_TARGET = 256 * 1024
MAX_BLOCK = 16 * 1024 * 1024
MAX_METADATA = 100_000
MAX_GROUP_VALUES = 1000


class CaptureFormatError(ValueError):
    pass


class BinaryCaptureWriter:
    """Write to a caller-owned binary file, buffering at most one small block."""

    def __init__(self, file: BinaryIO):
        self.file = file
        self.file.write(MAGIC)
        self._series: dict[tuple[str, str], int] = {}
        self._block = bytearray()
        self._group_key: tuple[float, str] | None = None
        self._values = bytearray()
        self._value_count = 0
        self._finished = False

    def write_values(self, values: Iterable[CapturedValue]) -> None:
        if self._finished:
            raise ValueError("Capture is already finished")
        for captured in values:
            metadata = (captured.label, captured.unit)
            series_id = self._series.get(metadata)
            if series_id is None:
                self._finish_group()
                if len(self._series) >= MAX_METADATA:
                    raise ValueError("Too many series definitions")
                series_id = len(self._series)
                label = captured.label.encode("utf-8")
                unit = captured.unit.encode("utf-8")
                self._append_record(b"S" + UINT.pack(series_id) + UINT.pack(len(label)) + label
                                    + UINT.pack(len(unit)) + unit)
                self._series[metadata] = series_id
            key = (captured.timestamp, captured.raw_text)
            if self._group_key != key or self._value_count >= MAX_GROUP_VALUES:
                self._finish_group()
                self._group_key = key
            self._values.extend(VALUE.pack(series_id, captured.value))
            self._value_count += 1

    def _finish_group(self) -> None:
        if self._group_key is None:
            return
        timestamp, raw_text = self._group_key
        raw = raw_text.encode("utf-8")
        self._append_record(b"R" + SAMPLE_HEADER.pack(timestamp, len(raw), self._value_count)
                            + raw + self._values)
        self._group_key = None
        self._values.clear()
        self._value_count = 0

    def _append_record(self, record: bytes) -> None:
        if len(record) > MAX_BLOCK:
            raise ValueError("Capture record exceeds the 16 MiB format limit")
        if len(self._block) + len(record) > BLOCK_TARGET:
            self._write_block()
        self._block.extend(record)
        if len(self._block) >= BLOCK_TARGET:
            self._write_block()

    def _write_block(self) -> None:
        if self._block:
            compressed = zlib.compress(self._block, level=1)
            self.file.write(BLOCK_HEADER.pack(len(self._block), len(compressed)))
            self.file.write(compressed)
            self._block.clear()

    def flush(self) -> None:
        """Publish complete blocks to the file without ending the capture."""
        if not self._finished:
            self._finish_group()
            self._write_block()
            self.file.flush()

    def finish(self) -> None:
        if not self._finished:
            self.flush()
            self.file.write(BLOCK_HEADER.pack(0, 0))
            self.file.flush()
            self._finished = True


def _read_exact(file: BinaryIO, size: int) -> bytes:
    data = file.read(size)
    if len(data) != size:
        raise CaptureFormatError("Incomplete capture: recording did not finish or the file is truncated")
    return data


def iter_binary_capture(path: str | Path, batch_size: int = 1000) -> Iterator[list[CapturedValue]]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    series: dict[int, tuple[str, str]] = {}
    batch = []
    with Path(path).open("rb") as file:
        if _read_exact(file, len(MAGIC)) != MAGIC:
            raise CaptureFormatError("Unsupported PlotTTY capture format or version")
        while True:
            raw_size, compressed_size = BLOCK_HEADER.unpack(_read_exact(file, BLOCK_HEADER.size))
            if raw_size == compressed_size == 0:
                if file.read(1):
                    raise CaptureFormatError("Unexpected data after end of capture")
                break
            if not 0 < raw_size <= MAX_BLOCK or not 0 < compressed_size <= MAX_BLOCK + 65536:
                raise CaptureFormatError("Invalid capture block size")
            compressed = _read_exact(file, compressed_size)
            decoder = zlib.decompressobj()
            try:
                data = decoder.decompress(compressed, raw_size + 1)
            except zlib.error as exc:
                raise CaptureFormatError("Damaged compressed capture block") from exc
            if len(data) != raw_size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise CaptureFormatError("Invalid compressed capture block")
            offset = 0

            def take(size):
                nonlocal offset
                if size < 0 or offset + size > len(data):
                    raise CaptureFormatError("Truncated record inside capture block")
                part = data[offset:offset + size]
                offset += size
                return part

            def text():
                size, = UINT.unpack(take(UINT.size))
                return take(size).decode("utf-8")

            try:
                while offset < len(data):
                    tag = take(1)
                    if tag == b"S":
                        series_id, = UINT.unpack(take(UINT.size))
                        if series_id != len(series) or len(series) >= MAX_METADATA:
                            raise CaptureFormatError("Invalid series definition")
                        series[series_id] = (text(), text())
                    elif tag == b"R":
                        timestamp, raw_length, count = SAMPLE_HEADER.unpack(take(SAMPLE_HEADER.size))
                        if not 0 < count <= MAX_GROUP_VALUES:
                            raise CaptureFormatError("Invalid sample value count")
                        raw_text = take(raw_length).decode("utf-8")
                        for series_id, value in VALUE.iter_unpack(take(count * VALUE.size)):
                            if series_id not in series:
                                raise CaptureFormatError("Sample refers to an undefined series")
                            label, unit = series[series_id]
                            batch.append(CapturedValue(timestamp, label, value, unit, raw_text))
                            if len(batch) >= batch_size:
                                yield batch
                                batch = []
                    else:
                        raise CaptureFormatError("Unknown capture record type")
            except UnicodeDecodeError as exc:
                raise CaptureFormatError("Invalid UTF-8 in capture metadata") from exc
            # Allow cancellation even through blocks containing only metadata.
            if not batch:
                yield []
        if batch:
            yield batch


class PlotSessionLog:
    def __init__(self, log_dir: Path | str = "logs"):
        self.log_dir = Path(log_dir)
        self.path: Path | None = None
        self._file: BinaryIO | None = None
        self._writer: BinaryCaptureWriter | None = None

    def start(self, port: str, baudrate: int) -> Path:
        self.close()
        self.path = create_log_path(self.log_dir, port, baudrate, "plot.plotty")
        self._file = self.path.open("xb")
        try:
            self._writer = BinaryCaptureWriter(self._file)
        except Exception:
            self._file.close()
            self._file = None
            raise
        return self.path

    def close(self) -> None:
        if self._file is None:
            return
        file, writer = self._file, self._writer
        self._file = self._writer = None
        try:
            writer.finish()
        finally:
            file.close()

    def flush(self) -> None:
        if self._writer is not None:
            self._writer.flush()

    def write_values(self, values: list[CapturedValue]) -> None:
        if self._writer is not None:
            self._writer.write_values(values)


class CaptureCancelled(Exception):
    pass


def export_capture_csv(source, destination, progress=None, cancelled=None) -> int:
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or (
        destination.exists() and os.path.samefile(source, destination)
    ):
        raise ValueError("Choose a different output file; the source must be preserved")
    descriptor, temporary = tempfile.mkstemp(prefix=".plottty_", suffix=".tmp", dir=destination.parent)
    row_count = 0
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(("timestamp", "label", "value", "unit", "raw_text"))
            for batch in iter_binary_capture(source):
                if cancelled is not None and cancelled():
                    raise CaptureCancelled()
                writer.writerows((v.timestamp, v.label, v.value, v.unit, v.raw_text) for v in batch)
                row_count += len(batch)
                if progress is not None:
                    progress(row_count)
            file.flush()
            os.fsync(file.fileno())
        if cancelled is not None and cancelled():
            raise CaptureCancelled()
        os.replace(temporary, destination)
        return row_count
    finally:
        Path(temporary).unlink(missing_ok=True)
