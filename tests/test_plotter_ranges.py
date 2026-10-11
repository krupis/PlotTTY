import unittest
from unittest.mock import patch

from modules.core.plotter import Plotter


class PlotterRangesTest(unittest.TestCase):
    def setUp(self):
        self.plotter = Plotter()
        self.addCleanup(self.plotter.close)

    def test_all_history_summary_does_not_flush_or_search(self):
        for i in range(1000):
            self.plotter.add_sample(i / 1000, float(i))
        with patch.object(self.plotter, '_flush_samples_to_file', side_effect=AssertionError('unnecessary disk access')):
            count, x, y = self.plotter.read_visible_samples(0, 1, 100)
        self.assertEqual(count, 1000)
        self.assertEqual((x[0], x[-1]), (0, .999))
        self.assertEqual((min(y), max(y)), (0, 999))

    def test_raw_reads_include_buffered_samples(self):
        self.plotter.add_sample(1, 42)
        self.assertEqual(self.plotter.read_visible_samples(0, 2, 100), (1, [1], [42]))
        self.plotter.add_sample(2, 43)
        self.assertEqual(self.plotter.read_visible_samples(0, 2, 100), (2, [1, 2], [42, 43]))

    def test_duplicate_timestamps_and_exact_boundaries(self):
        times = [0, 0, 1, 2, 2]
        for i, t in enumerate(times):
            self.plotter.add_sample(t, i)
        for start, end in [(-1, 3), (0, 0), (2, 2), (.5, 1.5), (-2, -1), (3, 4), (2, 1)]:
            expected = [(t, i) for i, t in enumerate(times) if start <= t <= end]
            count, x, y = self.plotter.read_visible_samples(start, end, 100)
            self.assertEqual(count, len(expected), (start, end))
            self.assertEqual(list(zip(x, y)), expected)

    def test_empty_capture(self):
        self.assertEqual(self.plotter.read_visible_samples(0, 1, 100), (0, [], []))

    def test_step_neighbors_span_sparse_gaps_without_changing_visible_count(self):
        for timestamp, value in [(0, 0), (4, 1), (8, 0)]:
            self.plotter.add_sample(timestamp, value)
        self.assertEqual(self.plotter.read_visible_samples(1, 3, 100, include_neighbors=True),
                         (0, [0, 4], [0, 1]))
        self.assertEqual(self.plotter.read_visible_samples(4, 4, 100, include_neighbors=True),
                         (1, [0, 4, 8], [0, 1, 0]))
        self.assertEqual(self.plotter.read_visible_samples(9, 10, 100, include_neighbors=True), (0, [], []))
        self.assertEqual(self.plotter.read_visible_samples(-2, -1, 100, include_neighbors=True), (0, [], []))

    def test_step_full_history_keeps_bucketed_reads_without_disk_access(self):
        for i in range(10000):
            self.plotter.add_sample(i*.001, (i//31)%2)
        with patch.object(self.plotter, '_flush_samples_to_file', side_effect=AssertionError('unnecessary disk access')):
            count, x, y = self.plotter.read_visible_samples(0, 10, 100, include_neighbors=True)
        self.assertEqual(count, 10000)
        self.assertLessEqual(len(x), 400)
        self.assertEqual(set(y), {0, 1})

    def test_disposal_discards_pending_samples_and_is_repeatable(self):
        self.plotter.add_sample(1, 42)
        with patch.object(self.plotter, "_write_pending_samples_to_file", side_effect=AssertionError("discarded data")):
            self.plotter.close()
            self.plotter.close()
        self.assertTrue(self.plotter._file.closed)
        self.assertEqual(self.plotter._pending_sample_bytes, b"")


if __name__ == '__main__':
    unittest.main()
