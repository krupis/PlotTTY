"""Keep compact summaries of samples for drawing large captures.

Bucket summarizes one consecutive group: its sample count and its first, last,
minimum and maximum points. Each point is a (timestamp, value) pair. These
representative points preserve endpoints and extrema, but not every oscillation.
Plotter keeps the raw samples separately for detailed reads.

Buckets holds lists of these summaries, grouped by target sample count:
    size 4:   [Bucket, Bucket, ...]
    size 8:   [Bucket, Bucket, ...]
    size 16:  [Bucket, Bucket, ...]

The last bucket in each list may still be filling (count < target size).
There is no separate pending state. When a bucket fills, it is passed to the
next size. For example, two completed size-4 buckets fill a size-8 bucket.
Because whole buckets are combined, the actual count can exceed a target when
adjacent target sizes are not exact multiples.

Reads choose a size, find overlapping buckets, and include unfinished buckets
from smaller sizes so the newest samples are visible immediately. If needed,
these buckets are grouped further to fit the caller's budget. Each group emits
up to four unique points ordered by timestamp, as separate x and y lists.

Samples must arrive in nondecreasing timestamp order for binary search to work.
Boundary buckets can include points outside the requested range. The caller
chooses the budget; this module does not know the screen's pixel width.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
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


class Buckets:
    """Store sample summaries at several sizes and read them for plotting."""

    def __init__(self) -> None:
        """Create an empty list for each target size, from smallest to largest."""
        self._buckets_by_size: dict[int, list[Bucket]] = {size: [] for size in BUCKET_SIZES}

    def add_sample(self, timestamp: float, value: float) -> None:
        """Fill the smallest bucket and pass completed buckets to larger sizes."""
        point = (timestamp, value)
        bucket = Bucket(1, point, point, point, point)
        for size, buckets in self._buckets_by_size.items():
            if buckets and buckets[-1].count < size:
                current = buckets[-1]
                bucket = Bucket(
                    current.count + bucket.count,
                    current.first,
                    bucket.last,
                    min(current.minimum, bucket.minimum, key=_point_y),
                    max(current.maximum, bucket.maximum, key=_point_y),
                )
                buckets[-1] = bucket
            else:
                buckets.append(bucket)
            if bucket.count < size:
                break

    def read_samples(
        self,
        start_time: float,
        end_time: float,
        samples_per_bucket: float,
        max_buckets: int,
    ) -> tuple[list[float], list[float]]:
        """Select a resolution and return reduced x/y lists for the time range."""
        level_index = min(bisect_left(BUCKET_SIZES, samples_per_bucket), len(BUCKET_SIZES) - 1)
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
        buckets = self._buckets_by_size[BUCKET_SIZES[level_index]]
        first_index = bisect_left(buckets, start_time, key=lambda bucket: bucket.last[0])
        last_index = bisect_right(buckets, end_time, key=lambda bucket: bucket.first[0])
        summaries = buckets[first_index:last_index]

        # Higher levels receive only completed lower-level buckets. Include
        # their unfinished tails so downsampling never delays the newest data.
        # The selected size's unfinished bucket was already included above.
        for size in reversed(BUCKET_SIZES[:level_index]):
            smaller_buckets = self._buckets_by_size[size]
            if not smaller_buckets:
                continue
            pending_bucket = smaller_buckets[-1]
            if (
                pending_bucket.count < size
                and pending_bucket.last[0] >= start_time
                and pending_bucket.first[0] <= end_time
            ):
                summaries.append(pending_bucket)
        return summaries


def _point_y(point: Point) -> float:
    """Extract the value for minimum/maximum comparisons, ignoring its timestamp."""
    return point[1]
