"""Summarize samples at several resolutions so large captures stay cheap to draw.

A bucket groups consecutive samples, not screen pixels or a fixed time interval.
Each point is a (timestamp, value) pair. Samples must arrive in nondecreasing
timestamp order so completed buckets can be searched with binary search.

Bucket is a compact record of one group: its raw sample count and its
first, last, lowest and highest points. Keeping the extrema preserves peaks and
dips; keeping the endpoints preserves how adjacent groups connect. These four
points can overlap, and the summary does not retain every oscillation inside
the group. Plotter stores the raw samples separately for detailed reads.

BucketLevel holds completed summaries at one target size and a single pending
Bucket (or None when empty). Sizes count raw samples, not summaries. Searches
use timestamps from the summaries directly instead of separate time indexes.
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


# Bucket is a summary of one consecutive group of raw samples.
class Bucket(NamedTuple):
    count: int
    first: Point
    last: Point
    minimum: Point
    maximum: Point


# BucketLevel is a collection of completed summaries at one target size, plus one unfinished bucket.
@dataclass
class BucketLevel:
    bucket_size: int
    summaries: list[Bucket] = field(default_factory=list)
    pending: Bucket | None = None

    def merge(self, bucket: Bucket) -> Bucket | None:
        """Accumulate a bucket; store and return it when full, otherwise return None."""
        if self.pending is not None:
            current = self.pending
            bucket = Bucket(
                current.count + bucket.count,
                current.first,
                bucket.last,
                min(current.minimum, bucket.minimum, key=_point_y),
                max(current.maximum, bucket.maximum, key=_point_y),
            )
        if bucket.count < self.bucket_size:
            self.pending = bucket
            return None

        self.summaries.append(bucket)
        self.pending = None
        return bucket


class BucketStore:
    """Accumulate summaries and return first/min/max/last points for a time range."""

    def __init__(self) -> None:
        """Create empty levels in order from the smallest bucket size to the largest."""
        self._bucket_levels = [BucketLevel(size) for size in BUCKET_SIZES]

    def add_sample(self, timestamp: float, value: float) -> None:
        """Wrap one sample as a summary and feed it into the smallest level."""
        point = (timestamp, value)
        bucket = Bucket(1, point, point, point, point)
        for level in self._bucket_levels:
            bucket = level.merge(bucket)
            if bucket is None:
                break

    def read_samples(
        self,
        start_time: float,
        end_time: float,
        samples_per_bucket: float,
        max_buckets: int,
    ) -> tuple[list[float], list[float]]:
        """Select a resolution and return reduced x/y lists for the time range."""
        level_index = min(bisect_left(BUCKET_SIZES, samples_per_bucket), len(self._bucket_levels) - 1)
        summaries = self._read_buckets(level_index, start_time, end_time)
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

    def _read_buckets(self, level_index: int, start_time: float, end_time: float) -> list[Bucket]:
        """Find completed and unfinished summaries overlapping the inclusive range."""
        completed = self._bucket_levels[level_index].summaries
        first_index = bisect_left(completed, start_time, key=lambda bucket: bucket.last[0])
        last_index = bisect_right(completed, end_time, key=lambda bucket: bucket.first[0])
        summaries = completed[first_index:last_index]

        # Higher levels receive only completed lower-level buckets. Include
        # their unfinished tails so downsampling never delays the newest data.
        for pending_level in reversed(self._bucket_levels[:level_index + 1]):
            pending_bucket = pending_level.pending
            if (
                pending_bucket is not None
                and pending_bucket.last[0] >= start_time
                and pending_bucket.first[0] <= end_time
            ):
                summaries.append(pending_bucket)
        return summaries


def _point_y(point: Point) -> float:
    """Extract the value for minimum/maximum comparisons, ignoring its timestamp."""
    return point[1]
