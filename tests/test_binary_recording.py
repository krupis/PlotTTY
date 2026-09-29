from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from modules.controllers.serial_session import SerialSession
from modules.core.binary_logging import iter_binary_capture
from modules.core.extraction import ExtractionRule
from modules.core.serial_log import SerialSessionLog


class BinaryRecordingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.session = SerialSession()
        self.session._receive_rate_timer.stop()
        self.session._log_flush_timer.stop()
        self.session.settings.log_to_file = True
        self.session._serial_log.log_dir = Path(self.directory.name)
        self.session._plot_log.log_dir = Path(self.directory.name)
        self.session.set_rules([ExtractionRule(label=f"Value {i}", mode="delimiter_column", extra_setting=str(i))
                                for i in range(6)])
        self.session._serial_log.start('TEST', 115200)
        self.path = self.session._plot_log.start('TEST', 115200)
        self.addCleanup(self.session.disconnect_serial)

    def test_recording_flush_and_disconnect_preserve_extracted_values(self):
        captured = []
        self.session.valuesCaptured.connect(captured.extend)
        data = ''.join(f'{i},3,3.2988,36.15,5.037846,114.672729\n' for i in range(2000)).encode()
        # Include partial serial lines across receive callbacks.
        for offset in range(0, len(data), 317):
            self.session.on_receive(data[offset:offset + 317], 1700000000 + offset / 100000)
        self.session.flush_logs()
        self.session.disconnect_serial()
        restored = [value for batch in iter_binary_capture(self.path) for value in batch]
        self.assertEqual(len(restored), 12000)
        self.assertEqual(restored, captured)

    def test_write_error_stops_recording_and_reports_it(self):
        errors = []
        self.session.errorOccurred.connect(errors.append)
        with patch.object(self.session._plot_log, 'flush', side_effect=OSError('disk full')):
            self.session.flush_logs()
        self.assertEqual(errors, ['Recording stopped: disk full'])
        self.assertIsNone(self.session._plot_log._file)

    def test_text_and_plot_flushed_by_same_timer(self):
        self.session.on_receive(b"1,2,3,4,5,6\n", 1)
        with patch.object(self.session._serial_log._file, "flush", wraps=self.session._serial_log._file.flush) as text_flush:
            self.session.on_receive(b"2,3,4,5,6,7\n", 2)
            text_flush.assert_not_called()
            self.session._log_flush_timer.timeout.emit()
            text_flush.assert_called_once()
        self.assertIn("1,2,3,4,5,6", self.session._serial_log.path.read_text())
        self.session.disconnect_serial()
        self.assertEqual(sum(len(batch) for batch in iter_binary_capture(self.path)), 12)

    def test_either_logger_write_or_flush_failure_closes_both(self):
        for name, method in (("_serial_log", "write_received"), ("_serial_log", "flush"),
                             ("_plot_log", "write_values"), ("_plot_log", "flush")):
            with self.subTest(logger=name, method=method):
                self.session._serial_log.start("TEST", 115200)
                self.session._plot_log.start("TEST", 115200)
                errors = []
                self.session.errorOccurred.connect(errors.append)
                with patch.object(getattr(self.session, name), method, side_effect=OSError("disk full")):
                    if method == "flush":
                        self.session.flush_logs()
                    else:
                        self.session.on_receive(b"1,2,3,4,5,6\n", 1)
                self.session.errorOccurred.disconnect(errors.append)
                self.assertEqual(errors, ["Recording stopped: disk full"])
                self.assertIsNone(self.session._serial_log._file)
                self.assertIsNone(self.session._plot_log._file)

    def test_both_close_attempted_after_close_error(self):
        text_file = self.session._serial_log._file
        plot_file = self.session._plot_log._file
        errors = []
        self.session.errorOccurred.connect(errors.append)
        def fail_after_close():
            text_file.close()
            raise OSError("text close failed")
        with patch.object(self.session._serial_log, "close", side_effect=fail_after_close), \
                patch.object(self.session._plot_log, "close", wraps=self.session._plot_log.close) as close_plot:
            self.session.disconnect_serial()
            close_plot.assert_called_once()
        self.assertTrue(plot_file.closed)
        self.assertEqual(errors, ["Recording stopped: text close failed"])

    def test_existing_recording_files_are_never_overwritten(self):
        for logger, module in ((self.session._serial_log, "serial_log"), (self.session._plot_log, "binary_logging")):
            path = Path(self.directory.name) / (module + ".existing")
            path.write_bytes(b"preserve")
            with patch(f"modules.core.{module}.create_log_path", return_value=path):
                with self.assertRaises(FileExistsError):
                    logger.start("TEST", 115200)
            self.assertEqual(path.read_bytes(), b"preserve")

    def test_same_time_text_reconnect_preserves_first_file(self):
        log = SerialSessionLog(self.directory.name)
        with patch("modules.core.serial_log.datetime") as clock:
            clock.now.return_value.strftime.return_value = "same_timestamp"
            first = log.start("TEST", 115200)
            log.write_received(b"first", "utf-8")
            second = log.start("TEST", 115200)
            log.write_received(b"second", "utf-8")
            log.close()
        self.assertNotEqual(first, second)
        self.assertIn("first", first.read_text())
        self.assertNotIn("second", first.read_text())



if __name__ == '__main__':
    unittest.main()
