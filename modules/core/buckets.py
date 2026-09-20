"""Keep compact summaries of samples for drawing large captures.

A Bucket summarizes consecutive samples with their first, last, lowest and
highest points. Buckets keeps a separate list for every target size. For each
incoming sample, every list either adds it to its unfinished last bucket or
starts a new bucket. For example, the size-4 list starts a new bucket after four
samples, while the size-8 list starts one after eight samples.

Reads choose an appropriate target size and return up to four representative
points from each selected group. Raw samples remain available in Plotter for
ranges that do not need downsampling.

Samples must arrive in nondecreasing timestamp order for binary search to work.
Boundary buckets can include points outside the requested range.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1_000, 10_000, 100_000, 1_000_000)

Point = tuple[float, float]


@dataclass(slots=True)
class Bucket:
    """Summary of one consecutive group of samples."""

    count: int
    first: Point
    last: Point
    minimum_point: Point
    maximum_point: Point

    def add_point(self, point: Point) -> None:
        """Include the next point in this bucket."""
        self.count += 1
        self.last = point
        if point[1] < self.minimum_point[1]:
            self.minimum_point = point
        if point[1] > self.maximum_point[1]:
            self.maximum_point = point


class Buckets:
    """Store bucket summaries at several target sizes."""

    def __init__(self) -> None:
        """Create one initially empty list for each target size."""

        self._levels = {}
        for size in BUCKET_SIZES:
            self._levels[size] = []

    def add_sample(self, timestamp: float, value: float) -> None:
        """Add a sample to the current bucket at every target size."""

        point = (timestamp, value)
        for target_size in BUCKET_SIZES:
            level = self._levels[target_size]

            if not level or level[-1].count == target_size:
                # If the last bucket is full or there are no buckets, create a new bucket with the current point as first, last, minimum, and maximum.
                level.append(Bucket(1, point, point, point, point))
            else:
                # If the last bucket is not full, add the current point to it.
                level[-1].add_point(point)

    def read_samples(
        self,
        start_index: int,
        stop_index: int,
        max_buckets: int,
    ) -> tuple[list[float], list[float]]:
        """Reduce samples in [start_index, stop_index) to at most max_buckets groups."""
        if stop_index <= start_index:
            return [], []

        max_buckets = max(1, max_buckets)
        samples_per_bucket = (stop_index - start_index) / max_buckets
        for size in BUCKET_SIZES:
            if size >= samples_per_bucket:
                break

        # Each level groups consecutive samples into fixed-size buckets.
        first_bucket = start_index // size
        stop_bucket = (stop_index + size - 1) // size
        selected_buckets = self._levels[size][first_bucket:stop_bucket]
        if not selected_buckets:
            return [], []

        # Boundary buckets and the largest level can still exceed the budget.
        group_size = max(1, math.ceil(len(selected_buckets) / max_buckets))
        x_values: list[float] = []
        y_values: list[float] = []
        for start in range(0, len(selected_buckets), group_size):
            group = selected_buckets[start : start + group_size]
            first = group[0].first
            last = group[-1].last
            minimum = min((bucket.minimum_point for bucket in group), key=lambda point: point[1])
            maximum = max((bucket.maximum_point for bucket in group), key=lambda point: point[1])

            for x_value, y_value in sorted({first, minimum, maximum, last}):
                x_values.append(x_value)
                y_values.append(y_value)

        return x_values, y_values
