"""Disk-backed per-series plot storage with bucketed reads."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
import math
import struct
import tempfile
from typing import NamedTuple


RAW_SAMPLE_STRUCT = struct.Struct("<dd")
BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1_000, 10_000, 100_000, 1_000_000)
PENDING_BYTES_LIMIT = 1024 * 1024

Point = tuple[float, float]


class BucketSummary(NamedTuple):
    count: int
    first: Point
    last: Point
    minimum: Point
    maximum: Point


@dataclass
class BucketLevel:
    bucket_size: int
    starts: list[float] = field(default_factory=list)
    ends: list[float] = field(default_factory=list)
    summaries: list[BucketSummary] = field(default_factory=list)
    current_count: int = 0
    current_first: Point | None = None
    current_last: Point | None = None
    current_minimum: Point | None = None
    current_maximum: Point | None = None

    def update_current_bucket(self, summary: BucketSummary) -> None:
        if self.current_count == 0:
            self.current_first = summary.first
            self.current_minimum = summary.minimum
            self.current_maximum = summary.maximum

        self.current_count += summary.count
        self.current_last = summary.last
        self.current_minimum = min(self.current_minimum, summary.minimum, key=_point_y)
        self.current_maximum = max(self.current_maximum, summary.maximum, key=_point_y)

    def is_current_bucket_full(self) -> bool:
        return self.current_count >= self.bucket_size

    def finish_current_bucket(self) -> BucketSummary:
        summary = self.current_summary()
        assert summary is not None

        self.starts.append(summary.first[0])
        self.ends.append(summary.last[0])
        self.summaries.append(summary)
        self.current_count = 0
        self.current_first = self.current_last = self.current_minimum = self.current_maximum = None
        return summary

    def current_summary(self) -> BucketSummary | None:
        if self.current_count == 0:
            return None

        assert self.current_first is not None
        assert self.current_last is not None
        assert self.current_minimum is not None
        assert self.current_maximum is not None
        return BucketSummary(
            count=self.current_count,
            first=self.current_first,
            last=self.current_last,
            minimum=self.current_minimum,
            maximum=self.current_maximum,
        )


class Plotter:
    """Store raw samples and read display-sized buckets for the visible time range."""

    def __init__(self):
        self._file = tempfile.TemporaryFile(prefix="plottty_series_", suffix=".bin")
        self._sample_count = 0
        self._pending_sample_bytes = bytearray()
        self._bucket_levels = [BucketLevel(bucket_size) for bucket_size in BUCKET_SIZES]

    def add_sample(self, timestamp: float, value: float) -> None:
        self._pending_sample_bytes.extend(RAW_SAMPLE_STRUCT.pack(timestamp, value))
        if len(self._pending_sample_bytes) >= PENDING_BYTES_LIMIT:
            self._write_pending_samples_to_file()

        self._sample_count += 1
        point = (timestamp, value)
        self._add_summary_to_bucket_level(
            0,
            BucketSummary(count=1, first=point, last=point, minimum=point, maximum=point),
        )

    def read_visible_samples(self, start_time: float, end_time: float, buckets: int) -> tuple[list[float], list[float]]:
        start_index, stop_index = self._sample_indexes_for_range(start_time, end_time)
        if stop_index <= start_index:
            return [], []

        visible_samples = stop_index - start_index
        bucket_count = max(1, buckets)
        samples_per_bucket = visible_samples / bucket_count
        if samples_per_bucket <= 1:
            return self._read_raw_samples_by_index(start_index, stop_index)

        bucket_level = self._select_bucket_level(samples_per_bucket)
        return self._read_bucket_level(bucket_level, start_time, end_time, bucket_count)

    def count_visible_samples(self, start_time: float, end_time: float) -> int:
        start_index, stop_index = self._sample_indexes_for_range(start_time, end_time)
        return max(0, stop_index - start_index)

    def latest_timestamp(self) -> float | None:
        if self._sample_count == 0:
            return None
        self._flush_samples_to_file()
        timestamp, _value = self._read_sample_at_index(self._sample_count - 1)
        return timestamp

    def sample_count(self) -> int:
        return self._sample_count

    def close(self) -> None:
        self._write_pending_samples_to_file()
        self._file.close()

    def _add_summary_to_bucket_level(self, level_index: int, summary: BucketSummary) -> None:
        level = self._bucket_levels[level_index]
        level.update_current_bucket(summary)
        if not level.is_current_bucket_full():
            return

        finished_summary = level.finish_current_bucket()
        next_level_index = level_index + 1
        if next_level_index < len(self._bucket_levels):
            self._add_summary_to_bucket_level(next_level_index, finished_summary)

    def _select_bucket_level(self, desired_samples_per_bucket: float) -> BucketLevel:
        for level in self._bucket_levels:
            if level.bucket_size >= desired_samples_per_bucket:
                return level
        return self._bucket_levels[-1]

    def _read_bucket_level(
        self,
        level: BucketLevel,
        start_time: float,
        end_time: float,
        max_buckets: int,
    ) -> tuple[list[float], list[float]]:
        summaries = self._read_bucket_summaries(level, start_time, end_time)
        if not summaries:
            return [], []

        group_size = max(1, math.ceil(len(summaries) / max(1, max_buckets)))
        x_values: list[float] = []
        y_values: list[float] = []
        for start in range(0, len(summaries), group_size):
            group = summaries[start : start + group_size]
            first = group[0].first
            last = group[-1].last
            minimum = min((summary.minimum for summary in group), key=_point_y)
            maximum = max((summary.maximum for summary in group), key=_point_y)

            for x_value, y_value in sorted({first, minimum, maximum, last}):
                x_values.append(x_value)
                y_values.append(y_value)

        return x_values, y_values

    def _read_bucket_summaries(self, level: BucketLevel, start_time: float, end_time: float) -> list[BucketSummary]:
        first_index = bisect_left(level.ends, start_time)
        last_index = bisect_right(level.starts, end_time)
        summaries = level.summaries[first_index:last_index]

        current_summary = level.current_summary()
        if current_summary is not None and current_summary.last[0] >= start_time and current_summary.first[0] <= end_time:
            summaries.append(current_summary)
        return summaries

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
        x_values: list[float] = []
        y_values: list[float] = []
        self._flush_samples_to_file()
        self._file.seek(start_index * RAW_SAMPLE_STRUCT.size)

        for _index in range(start_index, stop_index):
            data = self._file.read(RAW_SAMPLE_STRUCT.size)
            if len(data) != RAW_SAMPLE_STRUCT.size:
                break

            x_value, y_value = RAW_SAMPLE_STRUCT.unpack(data)
            x_values.append(x_value)
            y_values.append(y_value)

        return x_values, y_values

    def _sample_indexes_for_range(self, start_time: float, end_time: float) -> tuple[int, int]:
        self._flush_samples_to_file()
        return (
            self._find_sample_index(start_time, lower_bound=True),
            self._find_sample_index(end_time, lower_bound=False),
        )

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


def _point_y(point: Point) -> float:
    return point[1]
