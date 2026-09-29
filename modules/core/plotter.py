"""Disk-backed per-series plot storage with bucketed reads."""

from __future__ import annotations

import struct
import tempfile

from .buckets import Buckets


RAW_SAMPLE_STRUCT = struct.Struct("<dd")
PENDING_BYTES_LIMIT = 1024 * 1024


class Plotter:
    """Store raw samples and read display-sized buckets for the visible time range."""

    def __init__(self):
        self._file = tempfile.TemporaryFile(prefix="plottty_series_", suffix=".bin")
        self._sample_count = 0
        self.unit = ""
        self._latest_value: float | None = None
        self._first_timestamp: float | None = None
        self._latest_timestamp: float | None = None
        self._pending_sample_bytes = bytearray()
        self._buckets = Buckets()

    def add_sample(self, timestamp: float, value: float, unit: str = "") -> None:
        if self._first_timestamp is None:
            self._first_timestamp = timestamp
        self._pending_sample_bytes.extend(RAW_SAMPLE_STRUCT.pack(timestamp, value))
        if len(self._pending_sample_bytes) >= PENDING_BYTES_LIMIT:
            self._write_pending_samples_to_file()

        self.unit = unit or self.unit
        self._latest_value = value
        self._sample_count += 1
        self._latest_timestamp = timestamp
        self._buckets.add_sample(timestamp, value)

    def read_visible_samples(self, start_time: float, end_time: float, buckets: int) -> tuple[int, list[float], list[float]]:
        start_index, stop_index = self._sample_indexes_for_range(start_time, end_time)
        if stop_index <= start_index:
            return 0, [], []

        visible_samples = stop_index - start_index
        bucket_count = max(1, buckets)
        if visible_samples <= bucket_count:
            x_values, y_values = self._read_raw_samples_by_index(start_index, stop_index)
            return visible_samples, x_values, y_values

        x_values, y_values = self._buckets.read_samples(
            start_index, stop_index, bucket_count
        )
        return visible_samples, x_values, y_values

    def latest_value(self) -> float | None:
        """Exact latest captured value, independent of the viewed range."""
        return self._latest_value

    def latest_timestamp(self) -> float | None:
        return self._latest_timestamp

    def sample_count(self) -> int:
        return self._sample_count

    def close(self) -> None:
        self._write_pending_samples_to_file()
        self._file.close()

    def _write_pending_samples_to_file(self) -> None:
        if not self._pending_sample_bytes:
            return
        self._file.seek(0, 2)
        self._file.write(self._pending_sample_bytes)
        self._pending_sample_bytes.clear()

    def _flush_samples_to_file(self) -> None:
        self._write_pending_samples_to_file()
        self._file.flush()

    def _read_raw_samples_by_index(self, start_index: int, stop_index: int) -> tuple[list[float], list[float]]:
        """Flush only when raw data is actually needed, then read the range."""
        self._flush_samples_to_file()
        x_values: list[float] = []
        y_values: list[float] = []
        self._file.seek(start_index * RAW_SAMPLE_STRUCT.size)
        byte_count = (stop_index - start_index) * RAW_SAMPLE_STRUCT.size
        data = self._file.read(byte_count)

        for x_value, y_value in RAW_SAMPLE_STRUCT.iter_unpack(data):
            x_values.append(x_value)
            y_values.append(y_value)

        return x_values, y_values

    def _sample_indexes_for_range(self, start_time: float, end_time: float) -> tuple[int, int]:
        """Return an index slice including samples at both requested times."""
        if not self._sample_count:
            return 0, 0

        # An empty or completely out-of-capture range contains no samples.
        if start_time > end_time or end_time < self._first_timestamp or start_time > self._latest_timestamp:
            return 0, 0

        # "See all" already has known indexes; no disk access is needed.
        start_index = 0
        stop_index = self._sample_count
        if start_time <= self._first_timestamp and end_time >= self._latest_timestamp:
            return start_index, stop_index

        self._flush_samples_to_file()
        if start_time > self._first_timestamp:
            # First sample at or after start_time.
            start_index = self._find_sample_index(start_time, lower_bound=True)
        if end_time < self._latest_timestamp:
            # First sample after end_time, so equal timestamps are included.
            stop_index = self._find_sample_index(end_time, lower_bound=False)
        return start_index, stop_index

    def _find_sample_index(self, target_x: float, lower_bound: bool) -> int:
        low = 0
        high = self._sample_count

        while low < high:
            middle = (low + high) // 2
            x_value, _y_value = self._read_sample_at_index(middle)
            if x_value < target_x or (not lower_bound and x_value <= target_x):
                low = middle + 1
            else:
                high = middle

        return low

    def _read_sample_at_index(self, index: int) -> tuple[float, float]:
        if index < 0 or index >= self._sample_count:
            raise IndexError(index)

        self._file.seek(index * RAW_SAMPLE_STRUCT.size)
        data = self._file.read(RAW_SAMPLE_STRUCT.size)
        if len(data) != RAW_SAMPLE_STRUCT.size:
            raise IndexError(index)
        return RAW_SAMPLE_STRUCT.unpack(data)
