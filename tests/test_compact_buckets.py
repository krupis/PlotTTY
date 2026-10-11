"""Summary extrema and unfinished tails must match the raw source groups."""
import math
import unittest
from modules.core.buckets import Buckets, BUCKET_SIZES


def reference(samples, first, stop, budget):
    if stop <= first:
        return [], []
    budget = max(1, budget)
    size = next((s for s in BUCKET_SIZES if s >= (stop - first) / budget), BUCKET_SIZES[-1])
    groups = [samples[i:i + size] for i in range(0, len(samples), size)]
    groups = groups[first // size:(stop + size - 1) // size]
    step = max(1, math.ceil(len(groups) / budget))
    points = []
    for index in range(0, len(groups), step):
        raw = [point for group in groups[index:index + step] for point in group]
        points.extend(sorted({raw[0], raw[-1], min(raw, key=lambda p: p[1]), max(raw, key=lambda p: p[1])}))
    return [p[0] for p in points], [p[1] for p in points]


class CompactBucketsTest(unittest.TestCase):
    def test_extrema_boundaries_ties_and_unfinished_tails(self):
        for count in (1, 3, 4, 5, 7, 8, 9, 15, 16, 17, 31, 33, 63, 65, 127, 129, 8191, 8192, 8193, 9000):
            samples = [(i // 3, float(i % 17 - 8)) for i in range(count)]
            store = Buckets()
            for time, value in samples:
                store.add_sample(time, value)
            for budget in (1, 2, 5, 37, 1000):
                for first, stop in ((0, count), (count // 3, count), (0, max(1, count - 2))):
                    with self.subTest(count=count, budget=budget, first=first, stop=stop):
                        self.assertEqual(store.read_samples(first, stop, budget), reference(samples, first, stop, budget))

    def test_each_live_tail_is_visible_before_a_group_completes(self):
        store = Buckets()
        for i in range(130):
            store.add_sample(i * .0001, (-1) ** i * i)
            x, y = store.read_samples(0, i + 1, 1)
            self.assertEqual(x[-1], i * .0001)
            self.assertEqual((min(y), max(y)), (min((-1) ** j * j for j in range(i + 1)),
                                              max((-1) ** j * j for j in range(i + 1))))
