"""Disk history preserves text and locates sparse-index and search boundaries."""
import unittest
from modules.core.console_history import ConsoleHistory, ConsoleSearch


class ConsoleHistoryTest(unittest.TestCase):
    def setUp(self):
        self.history = ConsoleHistory()
        self.addCleanup(self.history.close)

    def test_unicode_windows_across_checkpoints_and_split_crlf(self):
        rows = [f'į🦊 {i}: ' + 'x' * (i % 13) for i in range(1500)]
        self.history.append('\r\n'.join(rows[:750]) + '\r', 0xFFFF0000)
        self.history.append('\n' + '\n'.join(rows[750:]) + '\n', 0xFFFFFFFF)
        self.history.file.flush()
        self.assertEqual(self.history.path.read_text(encoding='utf-8'), '\n'.join(rows) + '\n')
        self.assertEqual(len(self.history.offsets), 3)
        for first in (0, 1, 511, 512, 513, 749, 750, 1023, 1499, 1500):
            with self.subTest(first=first):
                segments = self.history.read(first, 10)
                text = ''.join(text for text, _ in segments)
                self.assertEqual(text, '\n'.join((rows + [''])[first:first + 10]))
                if text:
                    self.assertEqual(segments[0][1], 0xFFFF0000 if first < 750 else 0xFFFFFFFF)

    def test_search_snapshot_literal_matches_navigation_and_chunk_boundaries(self):
        rows = [f'r-{i:05d} į🦊' for i in range(6000)]
        for row in (511, 3000, 5999):
            rows[row] += ' KEY.*'
        self.history.append('\n'.join(rows) + '\n', 0xFFFFFFFF)
        self.history.file.flush()
        size = self.history.size
        self.history.append('KEY.*\n', 0xFFFFFFFF)
        self.history.file.flush()
        for current, backwards, row, number in (((0, 0), False, 511, 1),
                ((511, len(rows[511])), False, 3000, 2), ((0, 0), True, 5999, 3)):
            job = ConsoleSearch(self.history.path, size, 'key.*', current, backwards, None)
            job.run()
            self.assertIsNone(job.error)
            self.assertEqual(job.total, 3)
            self.assertEqual(job.match, (row, len(rows[row].split('KEY')[0].encode('utf-16-le')) // 2, 5, number))
