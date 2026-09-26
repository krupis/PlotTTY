from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication

from modules.controllers.serial_session import SerialSession
from modules.core.binary_logging import iter_binary_capture
from modules.core.models import ExtractionRule


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
        self.session.flush_plot_log()
        self.session.disconnect_serial()
        restored = [value for batch in iter_binary_capture(self.path) for value in batch]
        self.assertEqual(len(restored), 12000)
        self.assertEqual(restored, captured)

    def test_write_error_stops_recording_and_reports_it(self):
        errors = []
        self.session.errorOccurred.connect(errors.append)
        with patch.object(self.session._plot_log, 'flush', side_effect=OSError('disk full')):
            self.session.flush_plot_log()
        self.assertEqual(errors, ['Recording stopped: disk full'])
        self.assertIsNone(self.session._plot_log._file)


if __name__ == '__main__':
    unittest.main()
