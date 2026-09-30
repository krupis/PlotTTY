"""Behavior checks for the plot workspace and isolated rule editor."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import json
from threading import Event
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QObject, QPoint, QPointF, QSettings, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QPushButton

from mainwindow import MainWindow, apply_application_style
from modules.controllers.capture_job import CaptureJob
from modules.core.binary_logging import BinaryCaptureWriter
from modules.core.extraction import CapturedValue, ExtractionEngine, ExtractionRule
from modules.core.rule_suggestions import suggest_rules
from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.widgets.rules_editor import RulesEditor

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

    def editor(self, rules=None):
        editor = RulesEditor(rules if rules is not None else self.window.applied_rules, self.window)
        editor.rulesApplied.connect(self.window.apply_rules)
        self.addCleanup(editor.close)
        return editor

    def test_applied_rules_are_copied_for_profiles(self):
        rules = [ExtractionRule("original", "first_number", unit="V")]
        self.window.apply_rules(rules)
        rules[0].label = "caller mutation"
        path = Path(self.temp.name) / "profile.json"
        save_profile(AppProfile("test", self.window.applied_rules), path)
        self.assertEqual(load_profile(path).rules[0].label, "original")

    def test_generate_rules_requires_apply(self):
        editor = self.window.rules_editor
        original = self.window.applied_rules
        editor.sample.setPlainText("Voltage: 3.31 V Current: 0.14 A")
        editor.generate_rules()
        self.assertIs(self.window.applied_rules, original)
        self.assertTrue(editor.apply_rules())
        self.assertEqual([rule.label for rule in self.window.applied_rules], ["Voltage", "Current"])

    def test_rules_editor_is_persistent_in_extraction_sidebar(self):
        editor = self.window.rules_editor
        self.assertIs(editor.parentWidget(), self.window.ui.SeriesSidebar)
        self.assertTrue(editor.isVisible())
        self.assertIs(self.window.ui.SeriesList.parentWidget(), self.window.plot.series_selector)
        editor.table.item(0, 1).setText("inline")
        self.assertTrue(editor.apply_rules())
        self.assertEqual(self.window.applied_rules[0].label, "inline")

    def test_applying_a_rule_label_change_renames_existing_series(self):
        initial = [ExtractionRule("Value 0", "delimiter_column", extra_setting="0")]
        self.window.apply_rules(initial)
        self.window.plot.append_values([CapturedValue(1, "Value 0", 3.3)])
        renamed = [ExtractionRule("Voltage", "delimiter_column", extra_setting="0")]
        self.window.apply_rules(renamed)
        self.window.plot.append_values([CapturedValue(2, "Voltage", 3.4)])
        self.window.plot.on_refresh_pending_data()
        self.assertEqual([entry["label"] for entry in self.window.plot.series_info()], ["Voltage"])
        self.assertEqual(self.window.plot._series["Voltage"].sample_count(), 2)

    def test_rule_function_replaces_enable_and_x_reference_columns(self):
        dialog = self.editor([
            ExtractionRule("plot", "first_number"),
            ExtractionRule("time", "delimiter_column", sample_counter=True, extra_setting="0"),
        ])
        self.assertEqual(dialog.table.horizontalHeaderItem(0).text(), "Function")
        self.assertEqual(dialog.table.columnCount(), 5)
        self.assertEqual(dialog.table.cellWidget(0, 0).currentData(), "plot")
        self.assertEqual(dialog.table.cellWidget(1, 0).currentData(), "time")
        rules = dialog.rules_table.rules()
        self.assertTrue(rules[1].sample_counter)

    def test_invalid_rule_edit_does_not_commit(self):
        dialog = self.editor([ExtractionRule("bad", "regex", extra_setting="[")])
        previous = self.window.applied_rules
        for pattern in ("[", "no group"):
            dialog.table.item(0, 3).setText(pattern)
            self.assertFalse(dialog.apply_rules())
        self.assertIs(self.window.applied_rules, previous)
        dialog.table.item(0, 3).setText(r"(\d+)")
        self.assertTrue(dialog.apply_rules())
        dialog.rules_table.set_rules([ExtractionRule("x", "delimiter_column", extra_setting="-1")])
        self.assertFalse(dialog.apply_rules())
        dialog.table.item(0, 4).setText("1.5")
        self.assertFalse(dialog.apply_rules())
        dialog.table.item(0, 4).setText("0")
        self.assertTrue(dialog.apply_rules())

    def test_rule_selection_remove_and_x_reference(self):
        dialog = self.editor([ExtractionRule("time", "delimiter_column", sample_counter=True, extra_setting="0"),
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
        before = plot._time_range()
        point = QPointF(200, 10)
        event = QWheelEvent(point, point, QPoint(), QPoint(0,120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        plot.time_axis_label.wheelEvent(event)
        self.assertLess(plot._time_range()[1] - plot._time_range()[0], before[1] - before[0])
        self.assertEqual(plot._time_range(), plot.graph.time_range)
        self.assertFalse(plot.auto_scroll_button.isChecked())
        self.window.resize(1500, 900)
        APP.processEvents()
        plot.set_series_visible("s4", False)
        plot.set_series_visible("s4", True)

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
            session._connection.bytesReceived.emit(b"Voltage: 3.3 V\n", 100)
            w.ui.actionConsole.setChecked(True)
            w.ui.CommandEdit.setText("READ")
            w.ui.SendButton.click()
            self.assertEqual(session._connection.commands, ["READ"])
            w.ui.actionClearCapturedData.trigger()
            self.assertTrue(all(path.exists() for path in paths))
            w.ui.ConnectButton.click()
            self.assertFalse(session.is_connected)
            self.assertEqual(w._recording_label.text(), "Not recording")
            session.settings.raw_capture_mode = True
            w.ui.ConnectButton.click()
            session._connection.bytesReceived.emit(b"Voltage: 9 V\n", 101)
            self.assertEqual(w.plot.series_info(), [])
            with patch.object(session._plot_log, "flush", side_effect=OSError("disk full")), \
                    patch("mainwindow.QMessageBox.warning") as warning:
                session.flush_logs()
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

    def test_profile_file_actions_use_applied_rules_and_current_path(self):
        source = Path(self.temp.name) / "source.json"
        target = Path(self.temp.name) / "saved.json"
        save_profile(AppProfile("source", [ExtractionRule("value", "first_number", unit="V")]), source)
        with patch("mainwindow.QFileDialog.getOpenFileName", return_value=(str(source), "")):
            self.window.on_open_profile()
        self.assertEqual(self.window.profile_path, source)
        with patch("mainwindow.QFileDialog.getSaveFileName", return_value=(str(target), "")):
            self.window.on_save_profile_as()
        self.assertEqual(self.window.profile_path, target)
        self.assertEqual(load_profile(target).rules[0].label, "value")

    def test_profile_validation_rejects_invalid_rules_and_unknown_fields(self):
        path = Path(self.temp.name) / "bad.json"
        for rule in (ExtractionRule("bad", "regex", extra_setting="["),
                     ExtractionRule("bad", "regex", extra_setting="no group"),
                     ExtractionRule("bad", "delimiter_column", extra_setting="-1")):
            save_profile(AppProfile("invalid", [rule]), path)
            dialog = self.editor([rule])
            self.assertFalse(dialog.apply_rules())
            with self.assertRaises(ValueError):
                load_profile(path)
        previous = self.window.applied_rules
        with patch("mainwindow.QFileDialog.getOpenFileName", return_value=(str(path), "")), \
                patch("mainwindow.QMessageBox.warning"):
            self.window.on_open_profile()
        self.assertIs(self.window.applied_rules, previous)
        path.write_text(json.dumps({"rules": [{"label": "old", "pattern": "(.*)"}]}))
        with self.assertRaises(TypeError):
            load_profile(path)

    def test_generated_units_and_mode_changes(self):
        rules = suggest_rules("Voltage: 3.31 V  Current: 0.14 A")
        captured = ExtractionEngine(rules).extract("Voltage: 3.32 V  Current: 0.15 A")
        self.assertEqual([v.unit for v in captured], ["V", "A"])
        dialog = self.editor(rules)
        combo = dialog.table.cellWidget(0, 2)
        combo.setCurrentIndex(combo.findData("first_number"))
        self.assertEqual(dialog.table.item(0, 3).text(), "")
        self.assertFalse(dialog.table.item(0, 3).flags() & Qt.ItemFlag.ItemIsEditable)
        combo.setCurrentIndex(combo.findData("delimiter_column"))
        self.assertEqual(dialog.table.item(0, 3).text(), ",")
        self.assertEqual(dialog.table.item(0, 4).text(), "0")
        self.assertTrue(dialog.apply_rules())

    def test_console_fixed_limit_and_no_latency_monitor(self):
        self.window.console.append_received("\n".join(str(i) for i in range(50_100)))
        self.window.console.flush()
        editor = self.window.ui.ConsoleTextEdit
        self.assertEqual(editor.document().blockCount(), 50_000)
        self.assertEqual(editor.document().firstBlock().text(), "100")
        self.assertFalse(hasattr(self.window, "_latency_monitor"))
        self.assertFalse(hasattr(self.window.session.settings, "console_line_limit"))

    def test_shared_drag_and_manual_y_range(self):
        plot = self.window.plot
        plot.append_values([CapturedValue(i, "a", i) for i in range(20)])
        plot.on_refresh_pending_data()
        graph = plot.graph
        graph._y_ranges["a"] = (-10, 10)
        self.assertEqual(graph._y_range("a"), (-10, 10))
        plot._set_time_range(5, 15)
        graph.begin_drag(QPointF(300, 10))
        graph.drag_to(QPointF(200, 10))
        graph.end_drag()
        expected = plot._time_range()
        plot._set_time_range(5, 15)
        footer = plot.time_axis_label
        QTest.mousePress(footer, Qt.MouseButton.LeftButton, pos=QPoint(300, 10))
        QTest.mouseMove(footer, QPoint(200, 10))
        QTest.mouseRelease(footer, Qt.MouseButton.LeftButton, pos=QPoint(200, 10))
        self.assertEqual(plot._time_range(), expected)
        plot.append_values([CapturedValue(20, "a", 50)])
        plot.on_refresh_pending_data()
        self.assertEqual(graph._y_range("a"), (-10, 10))
        graph.clear_y_ranges()
        plot.fit_capture()
        self.assertGreater(graph._y_range("a")[1], 50)

    def test_progress_cancel_and_close_keep_worker_alive_until_finished(self):
        for operation in ("cancel_load", "cancel_export", "close_load"):
            with self.subTest(operation=operation):
                entered, release = Event(), Event()
                source = Path(self.temp.name) / "source.plotty"
                destination = Path(self.temp.name) / "existing.csv"
                destination.write_text("existing")
                def wait_for_release(job):
                    entered.set()
                    release.wait(5)
                    job._check_cancelled()
                self.window.plot.clear_values()
                self.window.plot.append_values([CapturedValue(0, "keep", 42)])
                with patch.object(CaptureJob, "_load", wait_for_release), \
                        patch("modules.controllers.capture_job.export_capture_csv", side_effect=lambda *args: wait_for_release(self.window._capture_job)):
                    self.window._start_capture_job(str(source), str(destination) if operation == "cancel_export" else None)
                    job = self.window._capture_job
                    self.assertTrue(entered.wait(2))
                    try:
                        if operation == "close_load":
                            self.window.close()
                            self.assertTrue(self.window.isVisible())
                        else:
                            button = self.window._loading_dialog.findChild(QPushButton)
                            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                        self.assertTrue(job.isInterruptionRequested())
                        self.assertTrue(job.isRunning())
                        self.assertIs(self.window._capture_job, job)
                    finally:
                        release.set()
                        self.assertTrue(job.wait(2000))
                    for _ in range(100):
                        APP.processEvents()
                        if self.window._capture_job is None:
                            break
                        QTest.qWait(10)
                self.assertIsNone(self.window._capture_job)
                self.assertEqual(destination.read_text(), "existing")
                if operation == "close_load":
                    self.assertFalse(self.window.isVisible())
                else:
                    self.assertEqual(self.window.plot.series_info()[0]["label"], "keep")

    def test_connection_controls_settings_and_layout_roundtrip(self):
        w = self.window
        w.on_open_serial_settings()
        dialog = w._serial_settings
        dialog.port_combo.addItem("test-port")
        dialog.port_combo.setCurrentText("test-port")
        dialog.baud_combo.setCurrentText("230400")
        dialog.refresh_ports()
        self.assertEqual(dialog.port_combo.currentText(), "test-port")
        self.assertEqual(w.session.settings.port, "")
        dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(w.session.settings.port, "test-port")
        self.assertEqual(w.session.settings.baudrate, 230400)
        self.assertIn("test-port · 230400", w.ui.ConnectionSettingsButton.text())
        w.on_connected_changed(True)
        self.assertFalse(w.ui.ConnectionSettingsButton.isEnabled())
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

    def test_connection_popover_drafts_and_styled_dropdown(self):
        apply_application_style(APP)
        self.addCleanup(lambda: APP.setStyleSheet(""))
        w = self.window
        with patch("modules.widgets.serial_settings_dialog.QSerialPortInfo.availablePorts", return_value=[]):
            w.on_open_serial_settings()
        dialog = w._serial_settings
        self.assertEqual(dialog.port_combo.count(), 0)
        self.assertEqual(dialog.port_combo.currentIndex(), -1)
        self.assertEqual(dialog.port_combo.placeholderText(), "Select port")
        self.assertTrue(dialog.parity_combo.isVisible())
        dialog.capture_toggle.click()
        dialog.baud_combo.setCurrentText("230400")
        dialog.parity_combo.setCurrentIndex(dialog.parity_combo.findData("E"))
        dialog.log_to_file_checkbox.setChecked(False)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(w.session.settings.baudrate, 115200)
        self.assertEqual(w.session.settings.parity, "N")
        self.assertTrue(w.session.settings.log_to_file)
        w.on_open_serial_settings()
        self.assertEqual(dialog.baud_combo.currentText(), "115200")
        dialog.baud_combo.showPopup()
        APP.processEvents()
        view = dialog.baud_combo.view()
        row_height = view.sizeHintForRow(0)
        self.assertGreaterEqual(view.viewport().height(), row_height * dialog.baud_combo.count())
        dialog.baud_combo.hidePopup()
        self.assertTrue(dialog.isVisible())
        dialog.parity_combo.setCurrentIndex(dialog.parity_combo.findData("E"))
        dialog.log_to_file_checkbox.setChecked(False)
        dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(w.session.settings.parity, "E")
        self.assertFalse(w.session.settings.log_to_file)


if __name__ == "__main__":
    unittest.main()
