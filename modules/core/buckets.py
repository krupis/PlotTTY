"""Summarize consecutive readings from one plotted series for fast drawing.

A size-4 bucket describes four readings over time, not four channels. For
example, readings 0..3 form the first bucket and readings 4..7 form the next.
Each bucket preserves its first, last, lowest and highest points; it does not
average their values. A size-8 bucket merges two completed size-4 buckets, and
larger sizes repeat that process.

A summary contains eight numbers in this order:
    (first_time, first_value, last_time, last_value,
     minimum_time, minimum_value, maximum_time, maximum_value)

Completed summaries are packed consecutively into numeric arrays. Only the
unfinished size-4 summary stays mutable. Reads also reconstruct unfinished
larger groups so their newest readings remain visible. Raw samples are stored
separately by Plotter. Timestamps must arrive in nondecreasing order.
"""
from array import array
import math

BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)


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
        self._levels = {size: array('d') for size in BUCKET_SIZES}
        self._count = 0
        self._partial = None

    def add_sample(self, timestamp, value):
        """Include one reading in the summaries without storing its raw data.

        Update the pending group's last point and extrema. On its fourth
        reading, store the completed size-4 summary and clear the pending one.
        Every eighth reading also completes a size-8 summary, every sixteenth
        a size-16 summary, and so on, by merging pairs of completed children.
        Larger levels are updated only when their groups finish.
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
        for size in BUCKET_SIZES[1:]:
            if self._count % size:
                # If this group is unfinished, all larger groups are too.
                break
            children = self._levels[size // 2]
            # Each child occupies eight numbers; merge the last two children.
            self._levels[size].extend(_merge(children[-16:-8], children[-8:]))

    def _tail(self, size):
        """Reconstruct the unfinished final bucket at the requested size.

        Start after the last completed bucket of this size. Merge the largest
        aligned smaller buckets covering the remaining readings, followed by
        _partial if needed. For example, 15 readings at size 16 use a completed
        size-8 bucket, a completed size-4 bucket and three pending readings.

        Return an eight-number tuple, or None if there is no unfinished bucket.
        This does not modify or store summaries, and does not read raw samples.
        """
        # Round down to the first reading after the completed size-N buckets.
        cursor = self._count // size * size
        summary = None
        while cursor < self._count:
            remaining = self._count - cursor
            if remaining < 4:
                part = self._partial
                cursor = self._count
            else:
                # Alignment prevents taking a child that overlaps earlier data.
                child_size = next(s for s in reversed(BUCKET_SIZES) if s <= remaining and cursor % s == 0)
                offset = cursor // child_size * 8
                part = self._levels[child_size][offset:offset + 8]
                cursor += child_size
            summary = tuple(part) if summary is None else _merge(summary, part)
        return summary

    def read_samples(self, start_index, stop_index, max_buckets):
        """Return representative timestamps and values for a sample-index range.

        The range is [start_index, stop_index): stop_index is exclusive. Pick
        the smallest stored bucket size that meets the requested group budget,
        or size 8192 when none is large enough. Include an unfinished tail and
        merge adjacent buckets further if needed to stay within max_buckets.
        Budgets below one are treated as one.

        Each output group contributes up to four distinct first/last/min/max
        points, sorted by timestamp and then value. Return two parallel lists:
        timestamps and values. An empty range produces two empty lists.

        Boundary buckets can include readings outside the requested range.
        This is a downsampled view, not an exact raw-sample slice; Plotter reads
        raw samples separately when enough detail can be drawn without buckets.
        """
        if stop_index <= start_index:
            return [], []
        max_buckets = max(1, max_buckets)
        samples_per_bucket = (stop_index - start_index) / max_buckets
        size = next((s for s in BUCKET_SIZES if s >= samples_per_bucket), BUCKET_SIZES[-1])
        # Include whole buckets touching the range, even at its boundaries.
        first_bucket = start_index // size
        stop_bucket = min((stop_index + size - 1) // size, math.ceil(self._count / size))
        if stop_bucket <= first_bucket:
            return [], []
        # Boundary buckets or the size-8192 limit can still exceed the budget.
        group_size = max(1, math.ceil((stop_bucket - first_bucket) / max_buckets))
        data = self._levels[size]
        completed = len(data) // 8
        tail = self._tail(size) if self._count % size else None
        x_values, y_values = [], []
        for start in range(first_bucket, stop_bucket, group_size):
            summary = None
            for bucket in range(start, min(stop_bucket, start + group_size)):
                # Only the final unfinished bucket is absent from the array.
                part = data[bucket * 8:bucket * 8 + 8] if bucket < completed else tail
                summary = tuple(part) if summary is None else _merge(summary, part)
            # One point may serve several roles; draw it only once per group.
            points = {(summary[i], summary[i + 1]) for i in (0, 2, 4, 6)}
            for x, y in sorted(points):
                x_values.append(x)
                y_values.append(y)
        return x_values, y_values
