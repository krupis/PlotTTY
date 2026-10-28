"""Receive-time display keeps chunk boundaries out of console lines and plot data."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QPlainTextEdit
from qt_cleanup import delete_qt_object
from mainwindow import MainWindow
from modules.controllers.connection_session import ConnectionSession
from modules.controllers.console_controller import ConsoleController
from modules.core.extraction import ExtractionRule
from modules.core.binary_logging import iter_binary_capture
from modules.core.line_decoder import LineDecoder

APP = QApplication.instance() or QApplication([])


class ReceiveTimestampTest(unittest.TestCase):
    def setUp(self):
        self.editor = QPlainTextEdit()
        self.addCleanup(delete_qt_object, self.editor)
        self.console = ConsoleController(self.editor, self.editor)
        self.addCleanup(self.console.close)
        self.console.set_receive_timestamps_visible(True)
        self.session = ConnectionSession()
        self.addCleanup(delete_qt_object, self.session)
        self.addCleanup(self.session.disconnect_device)
        self.session.settings.log_to_file = False
        self.session.receivedText.connect(self.console.append_received)

    def text(self):
        self.console.flush()
        return self.editor.toPlainText()

    def test_transport_receive_time_is_used_instead_of_gui_processing_time(self):
        with patch("modules.controllers.connection_session.time", return_value=9999999999):
            self.session.on_receive(None, b"136984,3,3.251200\r\n", 1793128867.75)
            self.session.on_receive(None, b"next\n", 1793128867.875)
        self.assertEqual(self.text(), "[1793128867.750] 136984,3,3.251200\n[1793128867.875] next\n")

    def test_partial_lines_keep_first_chunk_timestamp_and_split_crlf_has_no_extra_prefix(self):
        self.session.on_receive(None, b"first", 100.9)
        self.assertEqual(self.text(), "[100.900] first")
        self.session.on_receive(None, b" line\r", 101.1)
        self.session.on_receive(None, b"\nsecond\nthird", 102.5)
        self.session.on_receive(None, b" line\n", 103)
        self.assertEqual(self.text(), "[100.900] first line\n[102.500] second\n[102.500] third line\n")

    def test_incremental_unicode_decode_does_not_corrupt_console_or_extraction(self):
        self.session.set_rules([ExtractionRule("Reading", "first_number")])
        captured = []
        self.session.valuesCaptured.connect(captured.extend)
        data = "į: 3.25 🦊\n".encode()
        for index, byte in enumerate(data):
            self.session.on_receive(None, bytes([byte]), 200 + index)
        self.assertEqual(self.text(), "[201.000] į: 3.25 🦊\n")
        self.assertEqual(captured[0].value, 3.25)
        self.assertEqual(captured[0].raw_text, "į: 3.25 🦊")

    def test_blank_lines_get_timestamps_but_empty_tail_waits_for_next_chunk(self):
        self.session.on_receive(None, b"\n\n", 100)
        self.assertEqual(self.text(), "[100.000] \n[100.000] \n")
        self.session.on_receive(None, b"hello world\n\npartial", 101)
        self.session.on_receive(None, b" end\n", 102)
        self.assertEqual(
            self.text(),
            "[100.000] \n[100.000] \n[101.000] hello world\n"
            "[101.000] \n[101.000] partial end\n",
        )

    def test_prefix_never_changes_extracted_fields_receive_time_or_device_time(self):
        self.session.set_rules([ExtractionRule("First", "first_number")])
        captured = []
        self.session.valuesCaptured.connect(captured.extend)
        self.session.on_receive(None, b"136984,3,3.251200,13.743614\n", 1793128867.125)
        self.assertEqual((captured[-1].value, captured[-1].timestamp), (136984, 1793128867.125))
        self.session.set_rules([
            ExtractionRule("Voltage", "delimited_values", extra_setting="2"),
            ExtractionRule("Time", "delimited_values", is_time=True, extra_setting="3"),
        ])
        self.session.on_receive(None, b"136985,3,3.251200,13.743714\n", 1793128868)
        self.assertEqual((captured[-1].value, captured[-1].timestamp), (3.2512, 13.743714))
        self.assertEqual(captured[-1].raw_text, "136985,3,3.251200,13.743714")

    def test_toggle_affects_future_lines_and_clear_resets_partial_line_state(self):
        self.console.set_receive_timestamps_visible(False)
        self.session.on_receive(None, b"before", 100)
        self.console.set_receive_timestamps_visible(True)
        self.session.on_receive(None, b" continued\nnew\n", 101)
        self.console.set_receive_timestamps_visible(False)
        self.session.on_receive(None, b"after\n", 102)
        self.assertEqual(self.text(), "before continued\n[101.000] new\nafter\n")
        self.console.set_receive_timestamps_visible(True)
        self.session.on_receive(None, b"partial", 103)
        self.console.clear()
        self.session.on_receive(None, b"fresh\n", 104)
        self.assertEqual(self.text(), "[104.000] fresh\n")

    def test_timestamps_are_searchable_and_copied_with_the_line(self):
        self.session.on_receive(None, b"value: 3\n", 1793128867)
        self.text()
        spy = QSignalSpy(self.console.searchFinished)
        self.console.find_text("1793128867")
        if not spy.count():
            self.assertTrue(spy.wait(3000))
        self.assertEqual(self.editor.textCursor().selectedText(), "1793128867")
        self.editor.selectAll()
        self.editor.copy()
        self.assertEqual(APP.clipboard().text(), "[1793128867.000] value: 3\n")

    def test_recordings_keep_original_source_text(self):
        with TemporaryDirectory() as folder:
            self.session.settings.log_to_file = True
            self.session._serial_log.log_dir = Path(folder)
            self.session._plot_log.log_dir = Path(folder)
            text_path = self.session._serial_log.start("test")
            plot_path = self.session._plot_log.start("test")
            self.session.set_rules([ExtractionRule("Reading", "first_number")])
            try:
                self.session.on_receive(None, b"136984,3,3.251200\n", 1793128867)
            finally:
                self.session.disconnect_device()
            self.assertEqual(self.text(), "[1793128867.000] 136984,3,3.251200\n")
            values = [value for batch in iter_binary_capture(plot_path) for value in batch]
            self.assertEqual((values[0].value, values[0].timestamp), (136984, 1793128867))
            self.assertEqual(values[0].raw_text, "136984,3,3.251200")
            self.assertIn(" RX 136984,3,3.251200\n", text_path.read_text(encoding="utf-8"))

    def test_reconnect_resets_decoder_and_status_allows_next_line_prefix(self):
        self.session.on_receive(None, b"old partial", 100)
        self.console.append_status("[disconnected]\n")
        self.session._line_decoder = LineDecoder()
        self.session.on_receive(None, b"new\n", 101)
        self.assertEqual(self.text(), "[100.000] old partial[disconnected]\n[101.000] new\n")


class ReceiveTimestampPreferenceTest(unittest.TestCase):
    def test_view_switch_defaults_off_and_is_remembered(self):
        with TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "layout.ini"), QSettings.Format.IniFormat)
            with patch("mainwindow.QSettings", return_value=settings), \
                 patch("modules.widgets.rtt_settings_widget.RttSettingsWidget._load_targets"):
                for expected in (False, True):
                    window = MainWindow()
                    try:
                        APP.processEvents()
                        self.assertEqual(window._receive_timestamps_action.isChecked(), expected)
                        self.assertEqual(window.console_controller.show_receive_timestamps, expected)
                        self.assertIn(window._receive_timestamps_action, window.ui.menuView.actions())
                        window._receive_timestamps_action.setChecked(True)
                        window.session.settings.log_to_file = False
                        window.session.on_receive(None, b"sample\n", 1793128867)
                        window.console_controller.flush()
                        self.assertIn("[1793128867.000] sample", window.ui.ConsoleTextEdit.toPlainText())
                    finally:
                        window.close()
                        delete_qt_object(window)


if __name__ == "__main__":
    unittest.main()
