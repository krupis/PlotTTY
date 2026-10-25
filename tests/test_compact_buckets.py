"""Summary extrema and unfinished tails must match the raw source groups."""
import math
import unittest

import numpy as np
from modules.core.buckets import Buckets, BUCKET_SIZES


def reference(samples, first, stop, budget):
    if stop <= first:
        return [], []
    budget = max(1, budget)
    size = next((s for s in BUCKET_SIZES if s >= (stop - first) / budget), BUCKET_SIZES[-1])
    groups = [samples[i:i + size] for i in range(0, len(samples), size)]
    groups = groups[first // size:(stop + size - 1) // size]
    group_count = min(len(groups), budget)
    points = []
    for index in range(group_count):
        first_group = index * len(groups) // group_count
        stop_group = (index + 1) * len(groups) // group_count
        raw = [point for group in groups[first_group:stop_group] for point in group]
        points.extend(sorted({raw[0], raw[-1], min(raw, key=lambda p: p[1]), max(raw, key=lambda p: p[1])}))
    return [p[0] for p in points], [p[1] for p in points]


class CompactBucketsTest(unittest.TestCase):
    def test_requested_display_sizes_match_raw_groups_including_unfinished_tails(self):
        for size in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 2000, 4000, 8000, 16000):
            self.assertIn(size, BUCKET_SIZES)
            samples = [(i / 10000, float(i % 47 - 23)) for i in range(3 * size + 1)]
            store = Buckets()
            for point in samples:
                store.add_sample(*point)
            with self.subTest(size=size):
                x, y = store.read_samples(1, len(samples), 3)
                expected_x, expected_y = reference(samples, 1, len(samples), 3)
                np.testing.assert_array_equal(x, expected_x)
                np.testing.assert_array_equal(y, expected_y)
                self.assertEqual(x[-1], samples[-1][0])
                self.assertLessEqual(len(x), 12)

    def test_extra_boundary_bucket_does_not_halve_every_output_group(self):
        store = Buckets()
        for i in range(150000):
            store.add_sample(i, 3)
        x, y = store.read_samples(17, 146507, 293)
        self.assertEqual(len(x), 2 * 293)
        self.assertTrue(np.all(y == 3))
        self.assertEqual((x[0], x[-1]), (0, 146999))

    def test_screenshot_windows_no_longer_double_the_reduction_ratio(self):
        store = Buckets()
        for i in range(225000):
            store.add_sample(i, 3)
        ratios = []
        for first, stop in [(84000, 209000), (65000, 221250)]:
            x, _ = store.read_samples(first - 1, stop + 1, 293)
            ratios.append((stop - first) / len(x))
        self.assertTrue(240 < ratios[0] < 260)
        self.assertTrue(290 < ratios[1] < 310)
        self.assertLess(ratios[1] / ratios[0], 1.3)

    def test_extrema_boundaries_ties_and_unfinished_tails(self):
        for count in (1, 3, 4, 5, 7, 8, 9, 15, 16, 17, 31, 33, 63, 65, 127, 129, 8191, 8192, 8193, 9000, 65_539):
            samples = [(i // 3, float(i % 17 - 8)) for i in range(count)]
            store = Buckets()
            for time, value in samples:
                store.add_sample(time, value)
            for budget in (1, 2, 5, 37, 1000):
                for first, stop in ((0, count), (count // 3, count), (0, max(1, count - 2))):
                    with self.subTest(count=count, budget=budget, first=first, stop=stop):
                        x, y = store.read_samples(first, stop, budget)
                        expected_x, expected_y = reference(samples, first, stop, budget)
                        np.testing.assert_array_equal(x, expected_x)
                        np.testing.assert_array_equal(y, expected_y)

    def test_contiguous_buffers_remain_valid_while_live_levels_grow(self):
        store = Buckets()
        samples = [(i // 3, float(i % 17 - 8)) for i in range(600)]
        for point in samples[:500]:
            store.add_sample(*point)
        held_x, held_y = store.read_samples(200, 500, 30)
        expected_held = reference(samples[:500], 200, 500, 30)
        held100_x, held100_y = store.read_samples(100, 500, 4)
        expected100 = reference(samples[:500], 100, 500, 4)
        for i in range(500, 600):
            store.add_sample(*samples[i])
            x, y = store.read_samples(i - 250, i + 1, 30)
            expected_x, expected_y = reference(samples[:i + 1], i - 250, i + 1, 30)
            np.testing.assert_array_equal(x, expected_x)
            np.testing.assert_array_equal(y, expected_y)
            self.assertTrue(x.flags.c_contiguous and y.flags.c_contiguous)
            self.assertEqual(x.dtype, np.float64)
            self.assertEqual(y.dtype, np.float64)
        np.testing.assert_array_equal(held_x, expected_held[0])
        np.testing.assert_array_equal(held_y, expected_held[1])
        np.testing.assert_array_equal(held100_x, expected100[0])
        np.testing.assert_array_equal(held100_y, expected100[1])

    def test_empty_and_outside_ranges_return_empty_numeric_buffers(self):
        store = Buckets()
        store.add_sample(0, 1)
        for first, stop in [(0, 0), (1, 0), (4, 5)]:
            x, y = store.read_samples(first, stop, 1)
            self.assertEqual(x.shape, (0,))
            self.assertEqual(y.shape, (0,))
            self.assertEqual(x.dtype, np.float64)
            self.assertEqual(y.dtype, np.float64)

    def test_coarse_merge_preserves_first_nan_extrema_behavior(self):
        first_nan = [float(i) if i else float('nan') for i in range(20_000)]
        middle_nan = [float(i) for i in range(20_000)]
        middle_nan[8192], middle_nan[8193] = float('nan'), 1e9
        cases = [(first_nan, [(19_999, 19_999)]),
                 (middle_nan, [(0, 0), (19_999, 19_999)]),
                 ([float('nan')] * 20_000, [])]
        for values, expected in cases:
            with self.subTest(expected=expected):
                store = Buckets()
                for i, value in enumerate(values):
                    store.add_sample(i, value)
                x, y = store.read_samples(0, len(values), 1)
                self.assertEqual([(a, b) for a, b in zip(x, y) if math.isfinite(b)], expected)

    def test_infinite_values_and_signed_zero_ties_match_source_groups(self):
        patterns = [[0., -0., float('inf'), float('-inf'), 3., 3., -3., -3.],
                    [-0., 0., 0., -0., 0., -0., -0., 0.]]
        for values in patterns:
            samples = [(i // 3, values[i % len(values)]) for i in range(32_771)]
            store = Buckets()
            for point in samples:
                store.add_sample(*point)
            for first, stop, budget in [(0, 32_771, 1), (1, 32_770, 31), (801, 20_001, 1000)]:
                x, y = store.read_samples(first, stop, budget)
                expected_x, expected_y = reference(samples, first, stop, budget)
                np.testing.assert_array_equal(x, expected_x)
                np.testing.assert_array_equal(y, expected_y)
                self.assertEqual(y.tobytes(), np.asarray(expected_y, dtype=np.float64).tobytes())

    def test_each_live_tail_is_visible_before_a_group_completes(self):
        store = Buckets()
        for i in range(130):
            store.add_sample(i * .0001, (-1) ** i * i)
            x, y = store.read_samples(0, i + 1, 1)
            self.assertEqual(x[-1], i * .0001)
            self.assertEqual((min(y), max(y)), (min((-1) ** j * j for j in range(i + 1)),
                                              max((-1) ** j * j for j in range(i + 1))))
