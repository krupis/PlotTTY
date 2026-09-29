"""Behavior checks for the plot workspace and isolated rule editor."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, QPoint, QPointF, QSettings, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from mainwindow import MainWindow
from modules.controllers.capture_job import CaptureJob
from modules.core.binary_logging import BinaryCaptureWriter
from modules.core.models import CapturedValue, ExtractionRule
from modules.widgets.plot_widget import PlotWidget
from modules.widgets.rules_dialog import RulesDialog
from modules.widgets.serial_settings_dialog import SerialSettingsDialog

APP = QApplication.instance() or QApplication([])


class FakeTransport(QObject):
    bytesReceived = Signal(bytes, float)
    errorReceived = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.is_open = False
        self.commands = []

    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def write_text(self, command):
        self.commands.append(command)


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = QSettings(str(Path(self.temp.name) / "layout.ini"), QSettings.Format.IniFormat)
        self.patch = patch("mainwindow.QSettings", return_value=self.settings)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.window = MainWindow()
        self.window.resize(1280, 720)
        self.window.show()
        APP.processEvents()
        self.addCleanup(self.window.close)

    def dialog(self, rules=None):
        dialog = RulesDialog(rules if rules is not None else self.window.applied_rules, self.window)
        dialog.rulesApplied.connect(self.window.apply_rules)
        self.addCleanup(dialog.close)
        return dialog

    def test_apply_cancel_and_profile_draft_isolation(self):
        rules = [ExtractionRule("original", "first_number", unit="V")]
        self.window.apply_rules(rules)
        rules[0].label = "caller mutation"
        dialog = self.dialog()
        dialog.table.item(0, 2).setText("draft")
        path = Path(self.temp.name) / "profile.json"
        self.window.profile.save(path, self.window.applied_rules)
        self.assertEqual(self.window.profile.load(path).rules[0].label, "original")
        with patch.object(self.window.session, "set_rules", wraps=self.window.session.set_rules) as commit:
            self.assertTrue(dialog.apply_rules())
            commit.assert_called_once()
        dialog.table.item(0, 2).setText("unapplied")
        dialog.reject()
        self.assertEqual(self.window.applied_rules[0].label, "draft")
        self.assertEqual(self.window.session._engine.extract("1")[0].label, "draft")
        self.window.profile.save(path, self.window.applied_rules)
        self.window.apply_rules(self.window.profile.load(path).rules)
        self.assertEqual(self.window.applied_rules[0].unit, "V")

    def test_ok_cancel_and_generate(self):
        dialog = self.dialog()
        spy = QSignalSpy(dialog.rulesApplied)
        dialog.sample.setPlainText("Voltage: 3.31 V Current: 0.14 A")
        dialog.generate_rules()
        self.assertEqual(spy.count(), 0)
        dialog.accept()
        self.assertEqual(spy.count(), 1)
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)
        dialog = self.dialog()
        dialog.table.item(0, 2).setText("discarded")
        dialog.close()
        self.assertNotEqual(self.window.applied_rules[0].label, "discarded")

    def test_validation_keeps_dialog_open_and_does_not_commit(self):
        dialog = self.dialog([ExtractionRule("bad", "regex", extra_setting="[")])
        dialog.show()
        spy = QSignalSpy(dialog.rulesApplied)
        for pattern in ("[", "no group"):
            dialog.table.item(0, 4).setText(pattern)
            dialog.accept()
            self.assertIn("Row 1", dialog.error.text())
            self.assertTrue(dialog.isVisible())
        self.assertEqual(spy.count(), 0)
        dialog.table.item(0, 4).setText(r"(\d+)")
        self.assertTrue(dialog.apply_rules())
        dialog.rules_table.set_rules([ExtractionRule("x", "delimiter_column", extra_setting="-1")])
        self.assertFalse(dialog.apply_rules())
        dialog.table.item(0, 5).setText("1.5")
        self.assertFalse(dialog.apply_rules())
        dialog.table.item(0, 5).setText("0")
        self.assertTrue(dialog.apply_rules())

    def test_rule_selection_remove_and_x_reference(self):
        dialog = self.dialog([ExtractionRule("time", "delimiter_column", sample_counter=True, extra_setting="0"),
                              ExtractionRule("voltage", "delimiter_column", extra_setting="1")])
        self.assertTrue(dialog.apply_rules())
        captured = self.window.session._engine.extract("12,3.3")
        self.assertEqual((captured[0].timestamp, captured[0].value), (12, 3.3))
        dialog.table.selectRow(1)
        dialog.rules_table.remove_selected_rules()
        self.assertEqual(dialog.table.rowCount(), 1)

    def test_colors_hidden_capture_and_sidebar_structure(self):
        plot = self.window.plot
        self.window.session.settings.log_to_file = False
        self.window.session.on_receive(b"A: 1 V B: 2 A\n", 100)
        colors = [row["color"] for row in plot.series_info()]
        first = self.window.ui.SeriesList.item(0)
        plot.set_series_visible("A", False)
        self.assertIs(first, self.window.ui.SeriesList.item(0))
        self.window.session.on_receive(b"A: 3 V B: 4 A\n", 101)
        plot.on_refresh_pending_data()
        self.assertEqual(plot._series["A"].sample_count(), 2)
        self.assertEqual(plot._curves["B"].color, colors[1])
        self.assertEqual([row["color"] for row in plot.series_info()], colors)
        self.assertEqual(first.checkState(), Qt.CheckState.Unchecked)

    def test_live_and_loaded_units_exact_latest_in_old_view(self):
        values = [CapturedValue(100, "a", 1, "V"), CapturedValue(101, "a", 8.123456789, "mV"),
                  CapturedValue(102, "a", 3.987654321)]
        plot = self.window.plot
        plot.append_values(values)
        path = Path(self.temp.name) / "test.plotty"
        with path.open("wb") as file:
            writer = BinaryCaptureWriter(file)
            writer.write_values(values)
            writer.finish()
        loader = CaptureJob(path)
        loader.run()
        self.assertIsNone(loader.error)
        series = loader.take_series()
        self.assertEqual(series["a"].unit, plot._series["a"].unit)
        self.assertEqual(series["a"].latest_value(), 3.987654321)
        plot.replace_series(series, loader.start_time)
        plot._set_time_range(0, .5)
        self.assertEqual(plot._series["a"].latest_value(), 3.987654321)
        self.assertEqual(self.window.ui.SeriesList.item(0).text(), "a (mV)")
        self.assertIn("mV", plot._curves["a"].latest)

    def test_console_collapse_clear_and_commands(self):
        window = self.window
        self.assertFalse(window.ui.actionConsole.isChecked())
        window.session.settings.log_to_file = False
        window.session.on_receive(b"Voltage: 3 V\n", 100)
        window.console.flush()
        self.assertIn("Voltage", window.ui.ConsoleTextEdit.toPlainText())
        window.ui.actionConsole.setChecked(True)
        window.ui.ClearConsoleButton.click()
        self.assertEqual(window.ui.ConsoleTextEdit.toPlainText(), "")
        self.assertEqual(window.plot._series["Voltage"].sample_count(), 1)
        self.assertFalse(window.ui.SendButton.isEnabled())
        window.on_connected_changed(True)
        with patch.object(window.session, "send_command") as send:
            window.ui.CommandEdit.setText("first")
            QTest.keyClick(window.ui.CommandEdit, Qt.Key.Key_Return)
            window.ui.CommandEdit.setText("second")
            window.ui.SendButton.click()
            self.assertEqual([call.args[0] for call in send.call_args_list], ["first", "second"])
        window.ui.actionClearCapturedData.trigger()
        self.assertEqual(window.plot.series_info(), [])

    def test_scroll_shared_axis_and_y_hit_testing(self):
        plot = self.window.plot
        plot.append_values([CapturedValue(i, f"s{j}", i + j) for i in range(20) for j in range(12)])
        plot.on_refresh_pending_data()
        APP.processEvents()
        self.assertGreaterEqual(plot.graph.height(), 1800)
        footer_y = plot.time_axis_label.mapToGlobal(QPoint()).y()
        plot.scroll_area.verticalScrollBar().setValue(500)
        APP.processEvents()
        self.assertEqual(plot.time_axis_label.mapToGlobal(QPoint()).y(), footer_y)
        panel, rect = plot.graph.panel_geometry(4)
        point = QPointF(20, rect.center().y())
        self.assertEqual(plot.graph._panel_at(point)[0], "s4")
        event = QWheelEvent(point, point, QPoint(), QPoint(0,120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        plot.graph.wheelEvent(event)
        self.assertIn("s4", plot.graph._y_ranges)
        before = plot._time_range()
        point = QPointF(200, 10)
        event = QWheelEvent(point, point, QPoint(), QPoint(0,120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        plot.time_axis_label.wheelEvent(event)
        self.assertLess(plot._time_range()[1] - plot._time_range()[0], before[1] - before[0])
        self.assertEqual(plot._time_range(), plot.graph._time_range)
        self.assertFalse(plot.auto_scroll_button.isChecked())
        self.window.resize(1500, 900)
        APP.processEvents()
        plot.set_series_visible("s4", False)
        plot.set_series_visible("s4", True)
        self.assertIn("s4", plot.graph._y_ranges)

    def test_empty_single_and_all_hidden_render(self):
        plot = self.window.plot
        self.assertFalse(plot.grab().isNull())
        plot.append_values([CapturedValue(0, "constant", 42)])
        plot.on_refresh_pending_data()
        self.assertFalse(plot.grab().isNull())
        plot.set_series_visible("constant", False)
        self.assertEqual(plot.graph.empty_message, "No series selected")
        self.assertFalse(plot.grab().isNull())
        plot.clear_values()
        self.assertEqual(plot.graph.empty_message, "Waiting for series")

    def test_connection_recording_raw_mode_and_error_status(self):
        w = self.window
        session = w.session
        session.settings.port = "TEST"
        session._serial_log.log_dir = Path(self.temp.name)
        session._plot_log.log_dir = Path(self.temp.name)
        with patch("modules.controllers.serial_session.SerialTransport", FakeTransport):
            w.ui.ConnectButton.click()
            self.assertTrue(session.is_connected)
            self.assertIn("Recording", w._recording_label.text())
            paths = session.recording_paths
            self.assertEqual(len(paths), 2)
            self.assertIn(str(paths[-1]), w._recording_label.toolTip())
            session._transport.bytesReceived.emit(b"Voltage: 3.3 V\n", 100)
            w.ui.actionConsole.setChecked(True)
            w.ui.CommandEdit.setText("READ")
            w.ui.SendButton.click()
            self.assertEqual(session._transport.commands, ["READ"])
            w.ui.actionClearCapturedData.trigger()
            self.assertTrue(all(path.exists() for path in paths))
            w.ui.ConnectButton.click()
            self.assertFalse(session.is_connected)
            self.assertEqual(w._recording_label.text(), "Not recording")
            session.settings.raw_capture_mode = True
            w.ui.ConnectButton.click()
            session._transport.bytesReceived.emit(b"Voltage: 9 V\n", 101)
            self.assertEqual(w.plot.series_info(), [])
            with patch.object(session._plot_log, "flush", side_effect=OSError("disk full")), \
                    patch("mainwindow.QMessageBox.warning") as warning:
                session.flush_plot_log()
                self.assertIn("Recording stopped", warning.call_args.args[2])
            self.assertFalse(session.is_connected)
            self.assertEqual(w._recording_label.text(), "Not recording")

    def test_background_capture_load_and_export_actions(self):
        source = Path(self.temp.name) / "capture.plotty"
        with source.open("wb") as file:
            writer = BinaryCaptureWriter(file)
            writer.write_values([CapturedValue(1, "a", 1.23, "V")])
            writer.finish()
        self.window._start_capture_job(str(source))
        for _ in range(100):
            if self.window._capture_job is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.window._capture_job)
        self.assertEqual(self.window.plot.capture_title.text(), "capture.plotty")
        self.assertEqual(self.window.ui.SeriesList.item(0).text(), "a (V)")
        destination = source.with_suffix(".csv")
        self.window._start_capture_job(str(source), str(destination))
        for _ in range(100):
            if self.window._capture_job is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.window._capture_job)
        self.assertIn("1.23", destination.read_text())
        self.assertEqual(self.window.plot._series["a"].latest_value(), 1.23)

    def test_invalid_layout_and_keyboard_sidebar(self):
        self.settings.setValue("geometry", "invalid")
        self.settings.setValue("consoleHeight", "invalid")
        self.window.restore_layout()
        self.assertGreaterEqual(self.window.width(), 320)
        self.window.plot.append_values([CapturedValue(0, "a", 1)])
        sidebar = self.window.ui.SeriesList
        sidebar.setCurrentRow(0)
        sidebar.setFocus()
        QTest.keyClick(sidebar, Qt.Key.Key_Space)
        self.assertFalse(self.window.plot.series_info()[0]["visible"])
        QTest.keyClick(sidebar, Qt.Key.Key_Space)
        self.assertTrue(self.window.plot.series_info()[0]["visible"])
        self.window.ui.actionConsole.setChecked(True)
        self.window.on_connected_changed(True)
        self.window.ui.CommandEdit.setFocus()
        QTest.keyClick(self.window.ui.CommandEdit, Qt.Key.Key_Tab)
        self.assertIs(APP.focusWidget(), self.window.ui.SendButton)

    def test_connection_controls_settings_and_layout_roundtrip(self):
        w = self.window
        w.ui.PortCombo.addItem("test-port")
        w.ui.PortCombo.setCurrentText("test-port")
        w.ui.BaudCombo.setCurrentText("230400")
        w.refresh_ports()
        self.assertEqual(w.session.settings.port, "test-port")
        dialog = SerialSettingsDialog(w.session.settings)
        self.assertFalse(hasattr(dialog, "port_combo"))
        self.assertEqual(dialog.selected_settings().baudrate, 230400)
        dialog.close()
        w.on_connected_changed(True)
        self.assertFalse(w.ui.PortCombo.isEnabled())
        w.ui.actionConsole.setChecked(True)
        w.ui.actionDiagnostics.setChecked(True)
        w.ui.actionSidebar.setChecked(False)
        w.close()
        next_window = MainWindow()
        next_window.show()
        APP.processEvents()
        self.assertTrue(next_window.ui.actionConsole.isChecked())
        self.assertTrue(next_window.ui.actionDiagnostics.isChecked())
        self.assertFalse(next_window.ui.actionSidebar.isChecked())
        self.assertFalse(next_window.session.is_connected)
        self.assertEqual(next_window.plot.series_info(), [])
        next_window.close()


if __name__ == "__main__":
    unittest.main()
