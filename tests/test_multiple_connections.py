"""Independent serial sessions, tab routing, and safe multi-session shutdown."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mainwindow import MainWindow
from modules.controllers.capture_job import CaptureJob
from modules.core.binary_logging import iter_binary_capture
from modules.core.extraction import ExtractionRule
from qt_cleanup import delete_qt_object
from test_serial_acquisition import FakeSerial


APP = QApplication.instance() or QApplication([])


class MultipleConnectionsTest(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        preferences = QSettings(str(Path(self.directory) / "layout.ini"), QSettings.Format.IniFormat)
        self.enterContext(patch("mainwindow.QSettings", return_value=preferences))
        self.enterContext(patch("modules.widgets.connection_workspace.QSettings", return_value=preferences))
        self.enterContext(patch("modules.widgets.rtt_settings_widget.RttSettingsWidget._load_targets"))
        self.window = MainWindow()
        self.addCleanup(delete_qt_object, self.window)
        self.addCleanup(self.window.close)
        self.window.show()
        APP.processEvents()

    def configure(self, workspace, port):
        workspace.session.settings.transport.port = port
        workspace.session._serial_log.log_dir = Path(self.directory)
        workspace.session._plot_log.log_dir = Path(self.directory)
        workspace.apply_rules([ExtractionRule("Voltage", "named_values")])
        workspace._update_connection_target()

    def wait_for(self, predicate):
        for _ in range(200):
            if predicate():
                break
            QTest.qWait(5)
        self.assertTrue(predicate())

    def test_two_serial_ports_collect_record_and_send_independently(self):
        first = self.window.tabs.currentWidget()
        second = self.window.add_connection()
        self.configure(first, "COM14")
        self.configure(second, "COM15")
        self.assertEqual([self.window.tabs.tabText(i) for i in range(2)], ["COM14", "COM15"])
        with patch("modules.core.serial_transport.QSerialPort", FakeSerial), \
                patch("modules.widgets.connection_workspace.QMessageBox.warning"):
            first.session.connect_device()
            second.session.connect_device()
            self.assertTrue(first.session.is_connected)
            self.assertTrue(second.session.is_connected)
            self.assertFalse(first.plot._timer.isActive())
            self.assertFalse(first.console_controller._flush_timer.isActive())
            first_serial = first.session._connection._reader.serial
            second_serial = second.session._connection._reader.serial
            first_serial.incoming = b"Voltage: 14\n"
            second_serial.incoming = b"Voltage: 15\n"
            self.wait_for(lambda: "Voltage" in first.plot._series and "Voltage" in second.plot._series)
            self.assertEqual(first.plot._series["Voltage"].latest_value(), 14)
            self.assertEqual(second.plot._series["Voltage"].latest_value(), 15)
            paths = first.session.recording_paths + second.session.recording_paths
            self.assertEqual(len(set(paths)), 4)
            second.ui.CommandEdit.setText("READ15")
            second.on_send_command()
            self.wait_for(lambda: bool(second_serial.writes))
            self.assertEqual(second_serial.writes, [b"READ15\n"])
            self.assertEqual(first_serial.writes, [])
            self.assertEqual(first._command_history, [])
            self.assertEqual(second._command_history, ["READ15"])
            self.window.tabs.setCurrentWidget(first)
            APP.processEvents()
            self.assertTrue(first.plot._timer.isActive())
            self.assertFalse(second.plot._timer.isActive())
            self.assertIn("Voltage: 14", first.ui.ConsoleTextEdit.toPlainText())
            self.assertNotIn("Voltage: 15", first.ui.ConsoleTextEdit.toPlainText())
            first.session.on_transport_error(first.session._connection, "COM14 unplugged")
            self.assertFalse(first.session.is_connected)
            self.assertTrue(second.session.is_connected)
            self.window.close_connection(self.window.tabs.indexOf(first))
            self.assertEqual(self.window.tabs.count(), 1)
            self.assertIs(self.window.tabs.currentWidget(), second)
            second_serial.incoming = b"Voltage: 16\n"
            self.wait_for(lambda: second.plot._series["Voltage"].sample_count() == 2)
            second.session.disconnect_device()
            recorded_first = [value.value for batch in iter_binary_capture(paths[1]) for value in batch]
            recorded_second = [value.value for batch in iter_binary_capture(paths[3]) for value in batch]
            self.assertEqual(recorded_first, [14])
            self.assertEqual(recorded_second, [15, 16])

    def test_rules_settings_and_clear_are_per_tab_and_last_close_creates_blank_tab(self):
        first = self.window.tabs.currentWidget()
        self.configure(first, "COM14")
        first.ui.CommandTerminatorCombo.setCurrentIndex(first.ui.CommandTerminatorCombo.findData("\r\n"))
        first.session.settings.log_to_file = False
        first.session.on_receive(None, b"Voltage: 1\n", 100)
        second = self.window.add_connection()
        self.assertIsNot(first.session, second.session)
        self.assertEqual(second.applied_rules, [])
        self.assertEqual(second.session.settings.transport.port, "")
        self.configure(second, "COM15")
        second.session.settings.log_to_file = False
        second.session.on_receive(None, b"Voltage: 2\n", 200)
        second.on_clear_console_and_plot()
        self.assertEqual(second.plot.series_info(), [])
        self.assertEqual(first.plot._series["Voltage"].latest_value(), 1)
        self.assertEqual(first.session.settings.line_ending, "\r\n")
        self.window.tabs.tabBar().moveTab(0, 1)
        first._update_connection_target()
        self.assertEqual(self.window.tabs.tabText(self.window.tabs.indexOf(first)), "COM14")
        self.window.close_connection(self.window.tabs.indexOf(first))
        self.window.close_current_connection()
        self.assertEqual(self.window.tabs.count(), 1)
        self.assertEqual(self.window.tabs.currentWidget().plot.series_info(), [])
        self.assertEqual(self.window.tabs.currentWidget().session.settings.transport.port, "")

    def test_add_and_close_shortcuts(self):
        self.assertFalse(self.window.tabs.tabBar().drawBase())
        self.window.activateWindow()
        self.window.setFocus()
        QTest.qWait(10)
        QTest.keyClick(self.window, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.window.tabs.count(), 2)
        self.assertFalse(self.window.tabs.tabBar().drawBase())
        selected = self.window.tabs.currentWidget()
        QTest.keyClick(self.window, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(selected.ui.actionConsole.isChecked())
        self.assertTrue(selected.ui.SearchEdit.hasFocus())
        QTest.keyClick(self.window, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.window.tabs.count(), 1)

    def test_window_close_disconnects_every_serial_port(self):
        first = self.window.tabs.currentWidget()
        second = self.window.add_connection()
        self.configure(first, "COM14")
        self.configure(second, "COM15")
        with patch("modules.core.serial_transport.QSerialPort", FakeSerial):
            first.session.connect_device()
            second.session.connect_device()
            serials = [workspace.session._connection._reader.serial for workspace in (first, second)]
            histories = [workspace.console_controller._history.path for workspace in (first, second)]
            self.window.close()
            self.assertTrue(all(not serial.isOpen() for serial in serials))
            self.assertTrue(all(not path.exists() for path in histories))
            self.assertEqual(self.window.tabs.count(), 0)

    def test_window_close_waits_asynchronously_for_busy_capture_job(self):
        workspace = self.window.tabs.currentWidget()
        self.window.add_connection()
        source = Path(self.directory) / "capture.plotty"
        entered, release = Event(), Event()

        def wait_for_release(job):
            entered.set()
            release.wait(5)
            job._check_cancelled()

        with patch.object(CaptureJob, "_load", wait_for_release):
            workspace._start_capture_job(str(source))
            job = workspace._capture_job
            self.assertTrue(entered.wait(2))
            try:
                self.window.close()
                self.assertTrue(job.isInterruptionRequested())
                self.assertTrue(job.isRunning())
                self.assertTrue(self.window.isVisible())
            finally:
                release.set()
                self.assertTrue(job.wait(2000))
            self.wait_for(lambda: not self.window.isVisible())
        self.assertEqual(self.window.tabs.count(), 0)


if __name__ == "__main__":
    unittest.main()
