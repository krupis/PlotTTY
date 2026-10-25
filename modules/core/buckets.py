"""Summarize consecutive readings from one plotted series for fast drawing.

A size-4 bucket describes four readings over time, not four channels. For
example, readings 0..3 form the first bucket and readings 4..7 form the next.
Each bucket preserves its first, last, lowest and highest points; it does not
average their values. A size-8 bucket merges two completed size-4 buckets, and
larger sizes repeat that process.

A summary contains eight numbers in this order:
    (first_time, first_value, last_time, last_value,
     minimum_time, minimum_value, maximum_time, maximum_value)

An additional size-100 cache supplies the intermediate display sizes cheaply.
Completed summaries are packed consecutively into numeric arrays. Only the
unfinished size-4 summary stays mutable. Reads also reconstruct unfinished
larger groups so their newest readings remain visible. Raw samples are stored
separately by SeriesStore. Timestamps must arrive in nondecreasing order.
"""
from array import array
import math

import numpy as np

_STORAGE_BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)
# Intermediate display sizes combine stored binary and size-100 summaries.
BUCKET_SIZES = tuple(sorted({*_STORAGE_BUCKET_SIZES,
                            100, 200, 300, 400, 500, 600, 700, 800, 900,
                            1000, 2000, 4000, 8000, 16000}))


def _merge(left, right):
    """Return one summary covering two consecutive groups, left then right.

    Keep the left group's first point and the right group's last point. Choose
    the lower minimum and higher maximum from the children; ties keep the left
    child's point. Both inputs use the eight-number layout above and are left
    unchanged. The result is a tuple in the same layout.
    """
    minimum = right[4:6] if right[5] < left[5] else left[4:6]
    maximum = right[6:8] if right[7] > left[7] else left[6:8]
    return (left[0], left[1], right[2], right[3], minimum[0], minimum[1], maximum[0], maximum[1])


class Buckets:
    """Maintain several summary sizes for one series, independently of others."""

    def __init__(self):
        """Create empty summary arrays and an empty pending size-4 group.

        Each entry in _levels stores only completed buckets of that size.
        _count counts all readings, including those in the pending group.
        _partial is that group's summary, or None between groups.
        """
        self._levels = {size: array('d') for size in (*_STORAGE_BUCKET_SIZES, 100)}
        self._count = 0
        self._partial = None

    def add_sample(self, timestamp, value):
        """Include one reading in the summaries without storing its raw data.

        Update the pending group's last point and extrema. On its fourth
        reading, store the completed size-4 summary and clear the pending one.
        Every eighth reading also completes a size-8 summary, every sixteenth
        a size-16 summary, and so on, by merging pairs of completed children.
        Every hundredth reading also caches a size-100 summary from binary
        children. Larger levels are updated only when their groups finish.
        """
        # Every fourth completed reading leaves the next size-4 group empty.
        if self._count % 4 == 0:
            self._partial = [timestamp, value, timestamp, value, timestamp, value, timestamp, value]
        else:
            pending = self._partial
            pending[2], pending[3] = timestamp, value
            if value < pending[5]:
                pending[4], pending[5] = timestamp, value
            if value > pending[7]:
                pending[6], pending[7] = timestamp, value
        self._count += 1
        if self._count % 4:
            # Keep this summary mutable until all four readings have arrived.
            return
        self._levels[4].extend(self._partial)
        self._partial = None
        for size in _STORAGE_BUCKET_SIZES[1:]:
            if self._count % size:
                # If this group is unfinished, all larger groups are too.
                break
            children = self._levels[size // 2]
            # Each child occupies eight numbers; merge the last two children.
            self._levels[size].extend(_merge(children[-16:-8], children[-8:]))
        if self._count % 100 == 0:
            self._levels[100].extend(self._summarize_from(self._count - 100))

    def _tail(self, size):
        """Reconstruct the unfinished final bucket at the requested size.

        Start after the last completed bucket of this size. Merge the largest
        aligned smaller buckets covering the remaining readings, followed by
        _partial if needed. For example, 15 readings at size 16 use a completed
        size-8 bucket, a completed size-4 bucket and three pending readings.

        Return an eight-number tuple, or None if there is no unfinished bucket.
        This does not modify or store summaries, and does not read raw samples.
        """
        return self._summarize_from(self._count // size * size)

    def _summarize_from(self, cursor):
        """Combine aligned binary summaries through the latest reading."""
        summary = None
        while cursor < self._count:
            remaining = self._count - cursor
            if remaining < 4:
                part = self._partial
                cursor = self._count
            else:
                # Alignment prevents taking a child that overlaps earlier data.
                child_size = next(s for s in reversed(_STORAGE_BUCKET_SIZES) if s <= remaining and cursor % s == 0)
                offset = cursor // child_size * 8
                part = self._levels[child_size][offset:offset + 8]
                cursor += child_size
            summary = tuple(part) if summary is None else _merge(summary, part)
        return summary

    def read_samples(self, start_index, stop_index, max_buckets):
        """Return representative timestamps and values for a sample-index range.

        The range is [start_index, stop_index): stop_index is exclusive. Pick
        the smallest display bucket size that meets the requested group budget,
        or the largest size when none is large enough. Build display buckets
        from aligned stored children and include the unfinished tail. Distribute
        any further merges across the groups to stay within max_buckets.
        Budgets below one are treated as one.

        Each output group contributes up to four distinct first/last/min/max
        points, sorted by timestamp and then value. Return two parallel contiguous
        NumPy arrays: timestamps and values. Empty ranges produce empty arrays.

        Boundary buckets can include readings outside the requested range.
        This is a downsampled view, not an exact raw-sample slice; SeriesStore reads
        raw samples separately when enough detail can be drawn without buckets.
        """
        if stop_index <= start_index:
            return np.empty(0), np.empty(0)
        max_buckets = max(1, max_buckets)
        samples_per_bucket = (stop_index - start_index) / max_buckets
        size = next((s for s in BUCKET_SIZES if s >= samples_per_bucket), BUCKET_SIZES[-1])
        # Include whole display buckets touching the range, even at its boundaries.
        first_bucket = start_index // size
        stop_bucket = min((stop_index + size - 1) // size, math.ceil(self._count / size))
        if stop_bucket <= first_bucket:
            return np.empty(0), np.empty(0)
        # A divisible stored size covers each display bucket exactly.
        stored_size = max(s for s in self._levels if size % s == 0)
        children_per_bucket = size // stored_size
        first_child = first_bucket * children_per_bucket
        stop_child = min(stop_bucket * children_per_bucket, math.ceil(self._count / stored_size))
        data = self._levels[stored_size]
        completed = len(data) // 8
        summaries = np.frombuffer(data, dtype=np.float64).reshape(-1, 8)[first_child:stop_child]
        if stop_child > completed:
            summaries = np.vstack((summaries, self._tail(stored_size)))
        bucket_count = stop_bucket - first_bucket
        if children_per_bucket > 1 or bucket_count > max_buckets:
            group_count = min(bucket_count, max_buckets)
            # One extra boundary bucket merges locally, rather than doubling all groups.
            starts = (np.arange(group_count) * bucket_count // group_count) * children_per_bucket
            ends = np.r_[starts[1:], len(summaries)] - 1
            lengths = ends - starts + 1
            minima = np.fmin.reduceat(summaries[:, 5], starts)
            maxima = np.fmax.reduceat(summaries[:, 7], starts)
            indexes = np.arange(len(summaries))
            # Equal extrema keep the earliest child, as in incremental _merge.
            low = np.minimum.reduceat(np.where(
                summaries[:, 5] == np.repeat(minima, lengths), indexes, len(summaries)), starts)
            high = np.minimum.reduceat(np.where(
                summaries[:, 7] == np.repeat(maxima, lengths), indexes, len(summaries)), starts)
            # A NaN first extremum stays selected; later NaNs cannot replace it.
            low = np.where(np.isnan(summaries[starts, 5]), starts, low)
            high = np.where(np.isnan(summaries[starts, 7]), starts, high)
            summaries = np.column_stack((summaries[starts, :2], summaries[ends, 2:4],
                                         summaries[low, 4:6], summaries[high, 6:8]))
        points = summaries.reshape(-1, 4, 2)
        order = np.lexsort((points[:, :, 1], points[:, :, 0]), axis=1)
        points = np.take_along_axis(points, order[:, :, None], axis=1)
        distinct = np.ones(points.shape[:2], dtype=bool)
        distinct[:, 1:] = np.any(points[:, 1:] != points[:, :-1], axis=2)
        points = points[distinct]
        # Detach returned buffers so the packed levels can grow after this read.
        return points[:, 0].copy(), points[:, 1].copy()
