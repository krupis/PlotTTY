import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.controllers.capture_job import CaptureJob
from modules.core.binary_logging import BinaryCaptureWriter
from modules.core.extraction import CapturedValue


class CaptureJobTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "capture.plotty"

    def write_rows(self, rows):
        with self.path.open("wb") as file:
            writer = BinaryCaptureWriter(file)
            writer.write_values(CapturedValue(*row) for row in rows)
            writer.finish()

    def test_worker_prepares_relative_time_series_and_transfers_ownership(self):
        self.write_rows([(100, "a", 1), (100, "b", 2), (101, "a", 3)])
        loader = CaptureJob(self.path)
        loader.start()
        self.assertTrue(loader.wait(10000))
        self.assertIsNone(loader.error)
        self.assertEqual(loader.row_count, 3)
        self.assertEqual(loader.start_time, 100)
        stores = loader.take_series()
        for store in stores.values():
            self.addCleanup(store.close)
        self.assertEqual(loader.series, {})
        count, x, y = stores["a"].read_visible_samples(0, 2, 10)
        self.assertEqual((count, x.tolist(), y.tolist()), (2, [0, 1], [1, 3]))
        self.assertEqual(stores["b"].sample_count(), 1)

    def test_cancel_discards_partial_stores(self):
        self.write_rows([(i, "a", i) for i in range(3000)])
        loader = CaptureJob(self.path)
        with patch.object(loader, "isInterruptionRequested", side_effect=[False, True, True]):
            loader.run()
        self.assertTrue(loader.cancelled)
        self.assertGreater(loader.row_count, 0)
        self.assertEqual(loader.series, {})

    def test_parse_failure_discards_partial_stores(self):
        loader = CaptureJob(self.path)
        self.write_rows([(1, "a", 2)])
        value = CapturedValue(1, "a", 2)

        def failing_batches(_path):
            yield [value]
            raise OSError("test read failure")

        with patch("modules.controllers.capture_job.iter_binary_capture", failing_batches):
            loader.run()
        self.assertEqual(loader.error, "test read failure")
        self.assertEqual(loader.series, {})

    def test_same_worker_exports_csv_without_building_plot_stores(self):
        self.write_rows([(100, "a", 1), (101, "b", 2)])
        destination = self.path.with_suffix(".csv")
        job = CaptureJob(self.path, destination)
        job.start()
        self.assertTrue(job.wait(10000))
        self.assertIsNone(job.error)
        self.assertEqual(job.row_count, 2)
        self.assertEqual(job.series, {})
        self.assertIn("100.0,a,1.0", destination.read_text())

    def test_export_worker_cancellation_keeps_existing_destination(self):
        self.write_rows([(100, "a", 1)])
        destination = self.path.with_suffix(".csv")
        destination.write_text("existing")
        job = CaptureJob(self.path, destination)
        with patch.object(job, "isInterruptionRequested", return_value=True):
            job.run()
        self.assertTrue(job.cancelled)
        self.assertIsNone(job.error)
        self.assertEqual(destination.read_text(), "existing")


if __name__ == "__main__":
    unittest.main()
