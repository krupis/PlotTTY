"""Compact first/last/min/max summaries of completed sample groups.

Four-sample summaries are filled directly. Larger power-of-two summaries merge
two completed children. Numeric arrays avoid tracking a Python object graph for
every captured sample; only the unfinished four-sample group stays mutable.
Reads reconstruct an unfinished tail from smaller completed groups. Timestamps
must arrive in nondecreasing order, as required by Plotter's range lookup.
"""
from array import array
import math

BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)


def _merge(left, right):
    minimum = right[4:6] if right[5] < left[5] else left[4:6]
    maximum = right[6:8] if right[7] > left[7] else left[6:8]
    return (left[0], left[1], right[2], right[3], minimum[0], minimum[1], maximum[0], maximum[1])


class Buckets:
    def __init__(self):
        self._levels = {size: array('d') for size in BUCKET_SIZES}
        self._count = 0
        self._partial = None

    def add_sample(self, timestamp, value):
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
            return
        self._levels[4].extend(self._partial)
        self._partial = None
        for size in BUCKET_SIZES[1:]:
            if self._count % size:
                break
            children = self._levels[size // 2]
            self._levels[size].extend(_merge(children[-16:-8], children[-8:]))

    def _tail(self, size):
        cursor = self._count // size * size
        summary = None
        while cursor < self._count:
            remaining = self._count - cursor
            if remaining < 4:
                part = self._partial
                cursor = self._count
            else:
                child_size = next(s for s in reversed(BUCKET_SIZES) if s <= remaining and cursor % s == 0)
                offset = cursor // child_size * 8
                part = self._levels[child_size][offset:offset + 8]
                cursor += child_size
            summary = tuple(part) if summary is None else _merge(summary, part)
        return summary

    def read_samples(self, start_index, stop_index, max_buckets):
        if stop_index <= start_index:
            return [], []
        max_buckets = max(1, max_buckets)
        samples_per_bucket = (stop_index - start_index) / max_buckets
        size = next((s for s in BUCKET_SIZES if s >= samples_per_bucket), BUCKET_SIZES[-1])
        first_bucket = start_index // size
        stop_bucket = min((stop_index + size - 1) // size, math.ceil(self._count / size))
        if stop_bucket <= first_bucket:
            return [], []
        group_size = max(1, math.ceil((stop_bucket - first_bucket) / max_buckets))
        data = self._levels[size]
        completed = len(data) // 8
        tail = self._tail(size) if self._count % size else None
        x_values, y_values = [], []
        for start in range(first_bucket, stop_bucket, group_size):
            summary = None
            for bucket in range(start, min(stop_bucket, start + group_size)):
                part = data[bucket * 8:bucket * 8 + 8] if bucket < completed else tail
                summary = tuple(part) if summary is None else _merge(summary, part)
            points = {(summary[i], summary[i + 1]) for i in (0, 2, 4, 6)}
            for x, y in sorted(points):
                x_values.append(x)
                y_values.append(y)
        return x_values, y_values
