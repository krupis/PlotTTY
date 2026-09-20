"""Summarize samples at several resolutions so large captures stay cheap to draw.

A bucket groups consecutive samples, not screen pixels or a fixed time interval.
Each point is a (timestamp, value) pair. Samples must arrive in nondecreasing
timestamp order so the time indexes can be searched with binary search.

Bucket is a compact record of one group: its raw sample count and its
first, last, lowest and highest points. Keeping the extrema preserves peaks and
dips; keeping the endpoints preserves how adjacent groups connect. These four
points can overlap, and the summary does not retain every oscillation inside
the group. Plotter stores the raw samples separately for detailed reads.

BucketLevel holds completed summaries at one target size, their start/end time
indexes, and one unfinished bucket. Sizes count raw samples, not summaries.
For example, the size-4 level consumes individual samples; two finished size-4
summaries fill a size-8 bucket, and two size-8 summaries fill a size-16 bucket.
Higher levels consume whole summaries, so their actual bucket sizes can exceed
the target when adjacent target sizes are not exact multiples.

BucketStore manages this hierarchy:
  1. Add each sample to the smallest level. Pass completed buckets upward.
  2. For a display read, select a level using the requested samples per bucket.
  3. Find summaries overlapping the time range, including unfinished tails from
     lower levels so the newest samples do not wait for a large bucket to fill.
  4. Merge summaries if needed to fit the bucket budget. Return up to four unique
     points per group, ordered by timestamp, as separate x and y lists.

Boundary buckets may include points outside the requested time range because
whole summaries are used. The caller chooses the display budget; this module
does not know the plot's pixel width and does not modify the stored raw data.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
import math
from typing import NamedTuple


BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1_000, 10_000, 100_000, 1_000_000)

Point = tuple[float, float]


class Bucket(NamedTuple):
    """Sample count and representative points for one consecutive group."""

    count: int
    first: Point
    last: Point
    minimum: Point
    maximum: Point


@dataclass
class BucketLevel:
    """Completed summaries and an in-progress bucket at one target sample count."""

    bucket_size: int
    starts: list[float] = field(default_factory=list)
    ends: list[float] = field(default_factory=list)
    summaries: list[Bucket] = field(default_factory=list)
    current_count: int = 0
    current_first: Point | None = None
    current_last: Point | None = None
    current_minimum: Point | None = None
    current_maximum: Point | None = None

    def merge(self, summary: Bucket) -> None:
        """Merge the next summary into this level's unfinished bucket."""
        if self.current_count == 0:
            self.current_first = summary.first
            self.current_minimum = summary.minimum
            self.current_maximum = summary.maximum

        self.current_count += summary.count
        self.current_last = summary.last
        self.current_minimum = min(self.current_minimum, summary.minimum, key=_point_y)
        self.current_maximum = max(self.current_maximum, summary.maximum, key=_point_y)

    def is_full(self) -> bool:
        """Return whether the accumulated raw sample count meets the target."""
        return self.current_count >= self.bucket_size

    def finish_bucket(self) -> Bucket:
        """Store and index the nonempty bucket, then reset its accumulation state."""
        summary = self.pending_bucket()
        assert summary is not None

        self.starts.append(summary.first[0])
        self.ends.append(summary.last[0])
        self.summaries.append(summary)
        self.current_count = 0
        self.current_first = self.current_last = self.current_minimum = self.current_maximum = None
        return summary

    def pending_bucket(self) -> Bucket | None:
        """Snapshot the unfinished bucket without resetting it; return None if empty."""
        if self.current_count == 0:
            return None

        assert self.current_first is not None
        assert self.current_last is not None
        assert self.current_minimum is not None
        assert self.current_maximum is not None
        return Bucket(
            count=self.current_count,
            first=self.current_first,
            last=self.current_last,
            minimum=self.current_minimum,
            maximum=self.current_maximum,
        )


class BucketStore:
    """Accumulate summaries and return first/min/max/last points for a time range."""

    def __init__(self) -> None:
        """Create empty levels in order from the smallest bucket size to the largest."""
        self._bucket_levels = [BucketLevel(size) for size in BUCKET_SIZES]

    def add_sample(self, timestamp: float, value: float) -> None:
        """Wrap one sample as a summary and feed it into the smallest level."""
        point = (timestamp, value)
        self._add_to_level(
            0,
            Bucket(count=1, first=point, last=point, minimum=point, maximum=point),
        )

    def read_samples(
        self,
        start_time: float,
        end_time: float,
        samples_per_bucket: float,
        max_buckets: int,
    ) -> tuple[list[float], list[float]]:
        """Select a resolution and return reduced x/y lists for the time range."""
        level = self._select_level(samples_per_bucket)
        return self._read_level(level, start_time, end_time, max_buckets)

    def _add_to_level(self, level_index: int, summary: Bucket) -> None:
        """Accumulate a summary, forwarding completed buckets to the next level."""
        level = self._bucket_levels[level_index]
        level.merge(summary)
        if not level.is_full():
            return

        finished_summary = level.finish_bucket()
        next_level_index = level_index + 1
        if next_level_index < len(self._bucket_levels):
            self._add_to_level(next_level_index, finished_summary)

    def _select_level(self, desired_samples_per_bucket: float) -> BucketLevel:
        """Choose the first target size meeting the request, or the largest available."""
        for level in self._bucket_levels:
            if level.bucket_size >= desired_samples_per_bucket:
                return level
        return self._bucket_levels[-1]

    def _read_level(
        self,
        level: BucketLevel,
        start_time: float,
        end_time: float,
        max_buckets: int,
    ) -> tuple[list[float], list[float]]:
        """Group overlapping summaries and emit their unique endpoints and extrema."""
        summaries = self._read_buckets(level, start_time, end_time)
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

    def _read_buckets(self, level: BucketLevel, start_time: float, end_time: float) -> list[Bucket]:
        """Find completed and unfinished summaries overlapping the inclusive range."""
        first_index = bisect_left(level.ends, start_time)
        last_index = bisect_right(level.starts, end_time)
        summaries = level.summaries[first_index:last_index]

        # Higher levels receive only completed lower-level buckets. Include
        # their unfinished tails so downsampling never delays the newest data.
        level_index = self._bucket_levels.index(level)
        for pending_level in reversed(self._bucket_levels[:level_index + 1]):
            pending_bucket = pending_level.pending_bucket()
            if pending_bucket is not None and pending_bucket.last[0] >= start_time and pending_bucket.first[0] <= end_time:
                summaries.append(pending_bucket)
        return summaries
def _point_y(point: Point) -> float:
    """Extract the value for minimum/maximum comparisons, ignoring its timestamp."""
    return point[1]
