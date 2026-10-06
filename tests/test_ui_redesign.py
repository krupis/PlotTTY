"""Behavior checks for the plot workspace and isolated rule editor."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import json
from threading import Event
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtGui import QColor, QPalette, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QDialogButtonBox, QPushButton

from mainwindow import MainWindow, apply_application_style
from modules.controllers.capture_job import CaptureJob
from modules.controllers.connection_session import TRANSPORT_TYPES
from modules.core.binary_logging import BinaryCaptureWriter
from modules.core.extraction import CapturedValue, ExtractionEngine, ExtractionRule
from modules.core.rule_suggestions import suggest_rules
from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.core.transport import Transport
from modules.widgets.rules_editor import RulesEditor

APP = QApplication.instance() or QApplication([])


class FakeTransport(Transport):
    is_open = False
    connection_description = ""

    def __init__(self, settings, *, on_bytes_received, on_error, parent=None):
        super().__init__(settings, on_bytes_received=on_bytes_received, on_error=on_error, parent=parent)
        self.is_open = False
        self.commands = []
        self.connection_description = settings.port

    def open(self):
        self.is_open = True

    def close(self):
        super().close()
        self.is_open = False

    def write(self, data):
        self.commands.append(data)


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
        editor.rules_table.add_rule()
        self.assertIs(editor.parentWidget(), self.window.ui.SeriesSidebar)
        self.assertTrue(editor.isVisible())
        editor.table.item(0, 1).setText("inline")
        self.assertTrue(editor.apply_rules())
        self.assertEqual(self.window.applied_rules[0].label, "inline")

    def test_applying_a_rule_label_change_renames_existing_series(self):
        initial = [ExtractionRule("Value 0", "delimited_values", extra_setting="0")]
        self.window.apply_rules(initial)
        self.window.plot.append_values([CapturedValue(1, "Value 0", 3.3)])
        renamed = [ExtractionRule("Voltage", "delimited_values", extra_setting="0")]
        self.window.apply_rules(renamed)
        self.window.plot.append_values([CapturedValue(2, "Voltage", 3.4)])
        self.window.plot.on_refresh_pending_data()
        self.assertEqual([entry["label"] for entry in self.window.plot.series_info()], ["Voltage"])
        self.assertEqual(self.window.plot._series["Voltage"].sample_count(), 2)

    def test_rule_function_and_plot_visibility_columns(self):
        dialog = self.editor([
            ExtractionRule("plot", "first_number"),
            ExtractionRule("time", "delimited_values", is_time=True, extra_setting="0"),
        ])
        self.assertEqual(dialog.table.horizontalHeaderItem(0).text(), "Function")
        self.assertEqual(dialog.table.columnCount(), 7)
        self.assertEqual(dialog.table.cellWidget(0, 0).currentData(), "plot")
        self.assertEqual(dialog.table.cellWidget(1, 0).currentData(), "time")
        rules = dialog.rules_table.rules()
        self.assertTrue(rules[1].is_time)

    def test_invalid_rule_edit_does_not_commit(self):
        dialog = self.editor([ExtractionRule("bad", "regex_pattern", extra_setting="[")])
        previous = self.window.applied_rules
        for pattern in ("[", "no group"):
            dialog.table.item(0, 3).setText(pattern)
            self.assertFalse(dialog.apply_rules())
        self.assertIs(self.window.applied_rules, previous)
        dialog.table.item(0, 3).setText(r"(\d+)")
        self.assertTrue(dialog.apply_rules())
        dialog.rules_table.set_rules([ExtractionRule("x", "delimited_values", extra_setting="-1")])
        self.assertFalse(dialog.apply_rules())
        dialog.table.item(0, 4).setText("1.5")
        self.assertFalse(dialog.apply_rules())
        dialog.table.item(0, 4).setText("0")
        self.assertTrue(dialog.apply_rules())

    def test_rule_feedback_tracks_drafts_validation_and_apply(self):
        editor = self.window.rules_editor
        editor.rules_table.set_rules([ExtractionRule("value", "regex_pattern", extra_setting=r"(\d+)")])
        self.assertTrue(editor.apply_button.isEnabled())
        self.assertTrue(editor.apply_rules())
        self.assertFalse(editor.apply_button.isEnabled())
        self.assertTrue(editor.error_label.isHidden())
        applied = self.window.applied_rules
        editor.table.item(0, 3).setText("[")
        self.assertTrue(editor.apply_button.isEnabled())
        self.assertFalse(editor.apply_rules())
        self.assertFalse(editor.error_label.isHidden())
        self.assertTrue(editor.error_label.text())
        self.assertIs(self.window.applied_rules, applied)
        editor.table.item(0, 3).setText(r"(\d+)")
        self.assertTrue(editor.apply_rules())
        editor.table.cellWidget(0, 0).setCurrentIndex(1)
        self.assertTrue(editor.apply_button.isEnabled())
        self.assertTrue(editor.error_label.isHidden())
        editor.table.selectRow(0)
        editor.rules_table.remove_selected_rules()
        self.assertTrue(editor.apply_button.isEnabled())

    def test_apply_enables_only_for_changed_rules(self):
        editor = self.window.rules_editor
        editor.rules_table.add_rule()
        editor.apply_rules()
        self.assertFalse(editor.apply_button.isEnabled())
        label = editor.table.item(0, 1)
        original = label.text()
        label.setText("changed")
        self.assertTrue(editor.apply_button.isEnabled())
        label.setText(original)
        self.assertFalse(editor.apply_button.isEnabled())
        editor.rules_table.add_rule()
        self.assertTrue(editor.apply_button.isEnabled())
        editor.apply_button.click()
        self.assertFalse(editor.apply_button.isEnabled())
        self.assertEqual(len(self.window.applied_rules), 2)
        editor.table.selectRow(1)
        editor.rules_table.remove_selected_rules()
        self.assertTrue(editor.apply_button.isEnabled())

    def test_rule_table_grows_then_scrolls_and_shrinks(self):
        editor = self.window.rules_editor
        APP.processEvents()
        single_height = editor.table.height()
        editor.rules_table.set_rules([ExtractionRule(f"v{i}", "first_number") for i in range(40)])
        APP.processEvents()
        self.assertGreater(editor.table.height(), single_height)
        self.assertGreater(editor.table.verticalScrollBar().maximum(), 0)
        self.assertTrue(editor.rect().contains(editor.apply_button.geometry()))
        editor.rules_table.set_rules([ExtractionRule("one", "first_number")])
        APP.processEvents()
        self.assertLessEqual(editor.table.height(), single_height + 20)
        self.assertEqual(editor.table.verticalScrollBar().maximum(), 0)

    def test_rule_color_picker_is_draft_and_persists_in_profile(self):
        editor = self.window.rules_editor
        editor.rules_table.set_rules([ExtractionRule("Voltage", "first_number")])
        editor.apply_rules()
        self.window.plot.append_values([CapturedValue(1, "Voltage", 3.3)])
        original = self.window.plot.series_info()[0]["color"].name()
        swatch = editor.table.cellWidget(0, 5)
        with patch("modules.widgets.rules_table.QColorDialog.getColor", return_value=QColor("#ff8844")):
            swatch.click()
        self.assertTrue(editor.apply_button.isEnabled())
        self.assertEqual(self.window.plot.series_info()[0]["color"].name(), original)
        editor.apply_button.click()
        self.assertEqual(self.window.plot.series_info()[0]["color"].name(), "#ff8844")
        self.assertEqual(self.window.plot._curves["Voltage"].color.name(), "#ff8844")
        header = self.window.plot.graph.headers["Voltage"]
        APP.processEvents()
        self.assertEqual(header.palette().color(QPalette.ColorRole.WindowText).name(), "#ff8844")

        swatch = editor.table.cellWidget(0, 5)
        with patch("modules.widgets.rules_table.QMenu") as menu:
            menu.return_value.exec.return_value = menu.return_value.addAction.return_value
            swatch.customContextMenuRequested.emit(QPoint())
        self.assertEqual(swatch.property("color"), "")
        self.assertTrue(editor.apply_button.isEnabled())
        editor.apply_button.click()
        self.assertEqual(self.window.plot.series_info()[0]["color"].name(), original)
        APP.processEvents()
        self.assertEqual(header.palette().color(QPalette.ColorRole.WindowText).name(), original)
        with patch("modules.widgets.rules_table.QColorDialog.getColor", return_value=QColor("#ff8844")):
            swatch.click()
        editor.apply_button.click()
        self.assertEqual(self.window.plot._series["Voltage"].sample_count(), 1)
        path = Path(self.temp.name) / "colors.json"
        save_profile(AppProfile("colors", self.window.applied_rules), path)
        rules = load_profile(path).rules
        self.assertEqual(rules[0].color, "#ff8844")
        editor.rules_table.set_rules(rules)
        self.assertEqual(editor.table.cellWidget(0, 5).property("color"), "#ff8844")
        self.window.plot.set_rules([ExtractionRule("Voltage", "first_number", color="#ff8844", visible=False)])
        self.window.plot.set_rules([ExtractionRule("Voltage", "first_number", color="#ff8844")])
        self.assertEqual(self.window.plot._curves["Voltage"].color.name(), "#ff8844")

    def test_color_cancel_time_role_and_default_palette(self):
        editor = self.window.rules_editor
        editor.rules_table.set_rules([
            ExtractionRule("Time", "delimited_values", is_time=True, extra_setting="0"),
            ExtractionRule("Voltage", "first_number"),
        ])
        editor.apply_rules()
        self.assertTrue(editor.table.cellWidget(0, 5).isHidden())
        swatch = editor.table.cellWidget(1, 5)
        with patch("modules.widgets.rules_table.QColorDialog.getColor", return_value=QColor()):
            swatch.click()
        self.assertFalse(editor.apply_button.isEnabled())
        self.window.plot.append_values([CapturedValue(1, "Voltage", 3.3)])
        self.assertEqual(swatch.property("displayColor"), self.window.plot.series_info()[0]["color"].name())

    def test_named_rule_color_applies_to_multiple_series_and_validates_profile(self):
        self.window.apply_rules([ExtractionRule("Auto", "named_values", color="#bb66ee")])
        self.window.plot.append_values([CapturedValue(1, "A", 1), CapturedValue(1, "B", 2)])
        self.assertEqual([entry["color"].name() for entry in self.window.plot.series_info()], ["#bb66ee", "#bb66ee"])
        self.window.apply_rules([ExtractionRule("Auto", "named_values")])
        self.assertNotEqual(*[entry["color"].name() for entry in self.window.plot.series_info()])
        path = Path(self.temp.name) / "invalid-color.json"
        save_profile(AppProfile("bad", [ExtractionRule("A", color="not-a-color")]), path)
        with self.assertRaises(ValueError):
            load_profile(path)

    def test_rule_selection_remove_and_x_reference(self):
        dialog = self.editor([ExtractionRule("time", "delimited_values", is_time=True, extra_setting="0"),
                              ExtractionRule("voltage", "delimited_values", extra_setting="1")])
        self.assertTrue(dialog.apply_rules())
        captured = self.window.session._engine.extract("12,3.3")
        self.assertEqual((captured[0].timestamp, captured[0].value), (12, 3.3))
        dialog.table.selectRow(1)
        dialog.rules_table.remove_selected_rules()
        self.assertEqual(dialog.table.rowCount(), 1)

    def test_colors_hidden_capture_and_header_structure(self):
        self.window.apply_rules([ExtractionRule("Named values", "named_values")])
        plot = self.window.plot
        self.window.session.settings.log_to_file = False
        self.window.session.on_receive(None, b"A: 1 V B: 2 A\n", 100)
        colors = [row["color"] for row in plot.series_info()]
        plot.set_rules([ExtractionRule("A", "first_number", visible=False)])
        self.assertNotIn("A", plot.graph.headers)
        self.window.session.on_receive(None, b"A: 3 V B: 4 A\n", 101)
        plot.on_refresh_pending_data()
        self.assertEqual(plot._series["A"].sample_count(), 2)
        self.assertEqual(plot._curves["B"].color, colors[1])
        self.assertEqual([row["color"] for row in plot.series_info()], colors)

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
        self.assertEqual(self.window.plot.graph.headers["a"].text(), "a (mV)")
        self.assertIn("mV", plot._curves["a"].latest)

    def test_console_collapse_clear_and_commands(self):
        self.window.apply_rules([ExtractionRule("Named values", "named_values")])
        window = self.window
        self.assertFalse(window.ui.actionConsole.isChecked())
        window.session.settings.log_to_file = False
        window.session.on_receive(None, b"Voltage: 3 V\n", 100)
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

    def test_console_drag_to_border_keeps_panel_and_title_visible(self):
        window = self.window
        splitter = window.ui.WorkspaceSplitter
        window.ui.actionConsole.setChecked(True)
        APP.processEvents()
        handle = splitter.handle(1)
        self.assertGreater(splitter.sizes()[1], 0)
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        QTest.mouseMove(handle, QPoint(handle.width() // 2, splitter.height()))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton)
        APP.processEvents()
        self.assertGreater(splitter.sizes()[1], 0)
        self.assertFalse(splitter.collapsed)
        self.assertTrue(window.ui.actionConsole.isChecked())
        self.assertTrue(splitter.collapse_button.isVisible())
        self.assertTrue(window.ui.ConsoleTextEdit.isVisible())
        self.assertTrue(handle.isVisible())
        self.assertGreater(handle.height(), 0)
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        QTest.mouseMove(handle, QPoint(handle.width() // 2, -250))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton)
        APP.processEvents()
        self.assertGreater(splitter.sizes()[1], 0)
        self.assertTrue(window.ui.actionConsole.isChecked())

    def test_panel_buttons_collapse_reopen_and_follow_menu(self):
        for splitter, action, index in (
            (self.window.ui.MainSplitter, self.window.ui.actionSidebar, 0),
            (self.window.ui.WorkspaceSplitter, self.window.ui.actionConsole, 1),
        ):
            action.setChecked(True)
            APP.processEvents()
            button = splitter.collapse_button
            expanded = splitter.sizes()[index]
            QTest.mouseClick(button, Qt.LeftButton)
            APP.processEvents()
            self.assertGreater(splitter.sizes()[index], 0)
            self.assertLess(splitter.sizes()[index], expanded)
            self.assertTrue(splitter.collapsed)
            self.assertFalse(action.isChecked())
            self.assertTrue(splitter.handle(1).isVisible())
            self.assertTrue(button.isVisible())
            self.assertIn("Expand", button.accessibleName())
            handle = splitter.handle(1)
            size = splitter.sizes()[index]
            QTest.mousePress(handle, Qt.LeftButton, pos=handle.rect().center())
            QTest.mouseMove(handle, QPoint(-splitter.width(), splitter.height()))
            QTest.mouseRelease(handle, Qt.LeftButton)
            APP.processEvents()
            self.assertTrue(button.isVisible())
            self.assertTrue(splitter.collapsed)
            self.assertEqual(splitter.sizes()[index], size)
            QTest.mouseClick(button, Qt.LeftButton)
            APP.processEvents()
            self.assertTrue(action.isChecked())
            self.assertAlmostEqual(splitter.sizes()[index], expanded, delta=24)
            button.setFocus()
            QTest.keyClick(button, Qt.Key_Space)
            APP.processEvents()
            self.assertFalse(action.isChecked())
            self.assertTrue(splitter.collapsed)
            self.assertTrue(button.isVisible())
            self.assertIn("Expand", button.accessibleName())

    def test_sidebar_drag_and_collapsed_layout_restore(self):
        splitter = self.window.ui.MainSplitter
        handle = splitter.handle(1)
        QTest.mousePress(handle, Qt.LeftButton, pos=handle.rect().center())
        QTest.mouseMove(handle, QPoint(-splitter.width(), handle.height()//2))
        QTest.mouseRelease(handle, Qt.LeftButton)
        APP.processEvents()
        self.assertGreaterEqual(splitter.sizes()[0], 420)
        self.assertTrue(self.window.ui.actionSidebar.isChecked())
        self.assertTrue(self.window.rules_editor.isVisible())
        splitter.collapse_button.click()
        APP.processEvents()
        self.assertTrue(splitter.collapsed)
        self.assertTrue(splitter.collapse_button.isVisible())
        self.assertFalse(self.window.rules_editor.isVisible())
        self.window.close()
        restored = MainWindow()
        self.addCleanup(restored.close)
        restored.show()
        APP.processEvents()
        self.assertTrue(restored.ui.MainSplitter.collapsed)
        self.assertTrue(restored.ui.MainSplitter.collapse_button.isVisible())
        restored.ui.MainSplitter.collapse_button.click()
        APP.processEvents()
        self.assertGreaterEqual(restored.ui.MainSplitter.sizes()[0], 420)
        self.assertTrue(restored.rules_editor.isVisible())

    def test_collapsed_console_restores_and_search_reopens_it(self):
        window = self.window
        window.ui.actionConsole.setChecked(True)
        window.ui.actionConsole.setChecked(False)
        self.assertTrue(window.ui.WorkspaceSplitter.collapsed)
        self.assertTrue(window.ui.WorkspaceSplitter.collapse_button.isVisible())
        self.assertFalse(window.ui.ConsoleTextEdit.isVisible())
        window.close()
        restored = MainWindow()
        self.addCleanup(restored.close)
        restored.show()
        APP.processEvents()
        self.assertTrue(restored.ui.WorkspaceSplitter.collapsed)
        self.assertTrue(restored.ui.WorkspaceSplitter.collapse_button.isVisible())
        self.assertTrue(restored.ui.WorkspaceSplitter.handle(1).isVisible())
        restored.focus_console_search()
        APP.processEvents()
        self.assertGreater(restored.ui.WorkspaceSplitter.sizes()[1], 0)
        self.assertTrue(restored.ui.SearchEdit.hasFocus())
        self.assertFalse(restored.ui.WorkspaceSplitter.collapsed)
        self.assertTrue(restored.ui.ConsoleTextEdit.isVisible())

    def test_console_search_selects_and_navigates_matches(self):
        self.window.console.append_received("alpha beta alpha")
        self.window.console.flush()
        self.window.ui.SearchEdit.setText("alpha")
        self.assertEqual(self.window.ui.SearchMatchLabel.text(), "1/2")
        self.window.ui.SearchNextButton.click()
        self.assertEqual(self.window.ui.SearchMatchLabel.text(), "2/2")
        self.window.ui.SearchPreviousButton.click()
        self.assertEqual(self.window.ui.SearchMatchLabel.text(), "1/2")

    def test_clear_plot_keeps_console_text(self):
        self.window.console.append_received("keep this")
        self.window.console.flush()
        self.window.plot.append_values([CapturedValue(1, "value", 3.3)])
        self.window.plot.clear_plot_button.click()
        self.assertEqual(self.window.plot.series_info(), [])
        self.assertEqual(self.window.ui.ConsoleTextEdit.toPlainText(), "keep this")

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
        plot.set_rules([ExtractionRule("s4", "first_number", visible=False)])
        plot.set_rules([ExtractionRule("s4", "first_number")])

    def test_empty_single_and_all_hidden_render(self):
        plot = self.window.plot
        self.assertFalse(plot.grab().isNull())
        plot.append_values([CapturedValue(0, "constant", 42)])
        plot.on_refresh_pending_data()
        self.assertFalse(plot.grab().isNull())
        plot.set_rules([ExtractionRule("constant", "first_number", visible=False)])
        self.assertEqual(plot.graph.empty_message, "No series selected")
        self.assertFalse(plot.grab().isNull())
        plot.clear_values()
        self.assertEqual(plot.graph.empty_message, "Waiting for series")

    def test_switching_transports_preserves_each_saved_configuration(self):
        from modules.core.serial_transport import SerialSettings
        from modules.core.rtt_transport import RttSettings
        from modules.core.connection_settings import ConnectionSettings
        w = self.window
        w._connection_settings.set_settings(ConnectionSettings(
            transport=SerialSettings(port="COM123", baudrate=230400),
            encoding="latin-1", line_ending="\r\n", log_to_file=False,
        ))
        w._connection_settings.accept()
        QTest.keyClick(w.connection_type_combo, Qt.Key.Key_Down)
        self.assertIsInstance(w.session.settings.transport, RttSettings)
        w.on_open_connection_settings()
        dialog = w._connection_settings
        dialog.transport_widget.target_edit.setText("test-target")
        dialog.transport_widget.speed_spin.setValue(2000)
        dialog.accept()
        QTest.keyClick(w.connection_type_combo, Qt.Key.Key_Up)
        self.assertEqual(w.session.settings.transport.port, "COM123")
        self.assertEqual(w.session.settings.transport.baudrate, 230400)
        QTest.keyClick(w.connection_type_combo, Qt.Key.Key_Down)
        self.assertEqual(w.session.settings.transport.target, "test-target")
        self.assertEqual(w.session.settings.transport.speed_khz, 2000)
        self.assertEqual(w.session.settings.encoding, "latin-1")
        self.assertEqual(w.session.settings.line_ending, "\r\n")
        self.assertFalse(w.session.settings.log_to_file)
        self.assertFalse(hasattr(w.session.settings.transport, "port"))
        # Cancelling a draft must not alter the saved backend settings.
        w.on_open_connection_settings()
        dialog.transport_widget.target_edit.setText("discarded-target")
        dialog.reject()
        self.assertEqual(w.session.settings.transport.target, "test-target")

    def test_connection_recording_raw_mode_and_error_status(self):
        w = self.window
        session = w.session
        session.settings.transport.port = "TEST"
        session._serial_log.log_dir = Path(self.temp.name)
        session._plot_log.log_dir = Path(self.temp.name)
        with patch.dict(TRANSPORT_TYPES, {type(session.settings.transport): FakeTransport}):
            w.ui.ConnectButton.click()
            self.assertTrue(session.is_connected)
            self.assertEqual(w.ui.ConnectButton.text(), "Disconnect")
            self.assertIn("Recording", w._recording_label.text())
            paths = session.recording_paths
            self.assertEqual(len(paths), 2)
            self.assertIn(str(paths[-1]), w._recording_label.toolTip())
            session._connection.bytesReceived.emit(session._connection, b"Voltage: 3.3 V\n", 100)
            APP.processEvents()
            w.ui.actionConsole.setChecked(True)
            w.ui.CommandEdit.setText("READ")
            w.ui.SendButton.click()
            self.assertEqual(session._connection.commands, [b"READ\n"])
            w.ui.actionClearCapturedData.trigger()
            self.assertTrue(all(path.exists() for path in paths))
            w.ui.ConnectButton.click()
            self.assertFalse(session.is_connected)
            self.assertEqual(w._recording_label.text(), "Not recording")
            session.settings.raw_capture_mode = True
            w.ui.ConnectButton.click()
            session._connection.bytesReceived.emit(session._connection, b"Voltage: 9 V\n", 101)
            APP.processEvents()
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
        self.assertEqual(self.window.plot.graph.headers["a"].text(), "a (V)")
        destination = source.with_suffix(".csv")
        self.window._start_capture_job(str(source), str(destination))
        for _ in range(100):
            if self.window._capture_job is None:
                break
            QTest.qWait(10)
        self.assertIsNone(self.window._capture_job)
        self.assertIn("1.23", destination.read_text())
        self.assertEqual(self.window.plot._series["a"].latest_value(), 1.23)

    def test_table_visibility_keyboard_is_draft_until_applied(self):
        self.settings.setValue("geometry", "invalid")
        self.settings.setValue("consoleHeight", "invalid")
        self.window.restore_layout()
        editor = self.window.rules_editor
        editor.rules_table.set_rules([ExtractionRule("a", "first_number")])
        editor.apply_rules()
        self.window.plot.append_values([CapturedValue(0, "a", 1)])
        APP.processEvents()
        checkbox = editor.table.cellWidget(0, 6).findChild(QCheckBox)
        checkbox.setFocus()
        QTest.keyClick(checkbox, Qt.Key.Key_Space)
        self.assertFalse(editor.rules_table.rules()[0].visible)
        self.assertTrue(editor.apply_button.isEnabled())
        self.assertTrue(self.window.plot.series_info()[0]["visible"])
        editor.apply_button.click()
        self.assertEqual(self.window.plot.graph._panels, {})
        QTest.keyClick(checkbox, Qt.Key.Key_Space)
        editor.apply_button.click()
        self.assertTrue(self.window.plot.series_info()[0]["visible"])
        self.assertGreaterEqual(self.window.plot.graph._panels["a"].height(), 150)

    def test_table_visibility_mouse_hidden_capture_and_profile(self):
        window = self.window
        editor = window.rules_editor
        rules = [ExtractionRule("a", "regex_pattern", extra_setting=r"a: (\d+)"),
                 ExtractionRule("b", "regex_pattern", extra_setting=r"b: (\d+)")]
        editor.rules_table.set_rules(rules)
        editor.apply_rules()
        window.session.settings.log_to_file = False
        window.session.on_receive(None, b"a: 1 b: 2\n", 100)
        APP.processEvents()
        for row in range(2):
            checkbox = editor.table.cellWidget(row, 6).findChild(QCheckBox)
            QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton)
        editor.apply_button.click()
        self.assertEqual(window.plot._curves, {})
        self.assertEqual(window.plot.graph._panels, {})
        window.session.on_receive(None, b"a: 3 b: 4\n", 101)
        self.assertEqual(window.plot._series["a"].sample_count(), 2)
        self.assertEqual(window.plot._series["b"].sample_count(), 2)
        path = Path(self.temp.name) / "visibility.json"
        save_profile(AppProfile("hidden", window.applied_rules), path)
        self.assertTrue(all(not rule.visible for rule in load_profile(path).rules))
        editor.table.cellWidget(0, 6).findChild(QCheckBox).setChecked(True)
        editor.apply_button.click()
        window.plot.on_refresh_pending_data()
        self.assertEqual(set(window.plot._curves), {"a"})
        self.assertEqual(window.plot._curves["a"].latest, "3")
        window.plot.clear_values()
        self.assertEqual(editor.table.rowCount(), 2)
        window.session.on_receive(None, b"a: 5 b: 6\n", 102)
        self.assertEqual(set(window.plot._curves), {"a"})

    def test_named_rule_visibility_covers_future_series_and_loaded_capture(self):
        window = self.window
        editor = window.rules_editor
        editor.rules_table.set_rules([ExtractionRule("Named", "named_values", visible=False)])
        editor.apply_rules()
        window.session.settings.log_to_file = False
        window.session.on_receive(None, b"a: 1 b: 2\n", 100)
        self.assertEqual(window.plot._curves, {})
        window.session.on_receive(None, b"c: 3\n", 101)
        self.assertEqual(window.plot._curves, {})
        self.assertEqual(set(window.plot._series), {"a", "b", "c"})
        editor.table.cellWidget(0, 6).findChild(QCheckBox).setChecked(True)
        editor.apply_button.click()
        self.assertEqual(set(window.plot._curves), {"a", "b", "c"})
        editor.table.cellWidget(0, 6).findChild(QCheckBox).setChecked(False)
        editor.apply_button.click()
        from modules.core.plotter import Plotter
        store = Plotter()
        store.add_sample(0, 5)
        window.plot.replace_series({"loaded": store}, 0)
        self.assertEqual(window.plot._curves, {})
        editor.table.cellWidget(0, 6).findChild(QCheckBox).setChecked(True)
        editor.apply_button.click()
        self.assertEqual(set(window.plot._curves), {"loaded"})

    def test_time_row_has_no_active_visibility_checkbox(self):
        editor = self.window.rules_editor
        editor.rules_table.set_rules([ExtractionRule("Time", "first_number", is_time=True)])
        checkbox = editor.table.cellWidget(0, 6).findChild(QCheckBox)
        self.assertTrue(checkbox.isHidden())
        self.assertTrue(editor.table.cellWidget(0, 5).isHidden())
        editor.table.cellWidget(0, 0).setCurrentIndex(0)
        self.assertFalse(checkbox.isHidden())
        self.assertFalse(editor.table.cellWidget(0, 5).isHidden())

    def test_receiving_text_requires_explicit_extraction_rules(self):
        window = self.window
        window.session.settings.log_to_file = False
        self.assertEqual(window.applied_rules, [])
        self.assertEqual(window.rules_editor.rules_table.rules(), [])
        window.session.on_receive(None, b"[Initialize:123] Voltage: 3 V\n", 100)
        window.console.flush()
        self.assertIn("Initialize", window.ui.ConsoleTextEdit.toPlainText())
        self.assertEqual(window.plot.series_info(), [])
        window.rules_editor.rules_table.set_rules([ExtractionRule("Voltage", "regex_pattern", extra_setting=r"Voltage: (\d+)")])
        window.rules_editor.apply_button.click()
        window.session.on_receive(None, b"[Initialize:123] Voltage: 4 V\n", 101)
        self.assertEqual([entry["label"] for entry in window.plot.series_info()], ["Voltage"])

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
        for rule in (ExtractionRule("bad", "regex_pattern", extra_setting="["),
                     ExtractionRule("bad", "regex_pattern", extra_setting="no group"),
                     ExtractionRule("bad", "delimited_values", extra_setting="-1")):
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

    def test_generated_units_and_method_changes(self):
        rules = suggest_rules("Voltage: 3.31 V  Current: 0.14 A")
        captured = ExtractionEngine(rules).extract("Voltage: 3.32 V  Current: 0.15 A")
        self.assertEqual([v.unit for v in captured], ["V", "A"])
        dialog = self.editor(rules)
        combo = dialog.table.cellWidget(0, 2)
        combo.setCurrentIndex(combo.findData("first_number"))
        self.assertEqual(dialog.table.item(0, 3).text(), "")
        self.assertFalse(dialog.table.item(0, 3).flags() & Qt.ItemFlag.ItemIsEditable)
        combo.setCurrentIndex(combo.findData("delimited_values"))
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
        w.on_open_connection_settings()
        dialog = w._connection_settings
        dialog.transport_widget.port_combo.addItem("test-port", "test-port")
        dialog.transport_widget.port_combo.setCurrentText("test-port")
        dialog.transport_widget.baud_combo.setCurrentText("230400")
        dialog.transport_widget.refresh_button.click()
        self.assertEqual(dialog.transport_widget.port_combo.currentText(), "test-port")
        self.assertEqual(w.session.settings.transport.port, "")
        dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(w.session.settings.transport.port, "test-port")
        self.assertEqual(w.session.settings.transport.baudrate, 230400)
        self.assertEqual(w.ui.ConnectionSettingsButton.text(), "Connection settings")
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
        with patch("modules.widgets.serial_settings_widget.QSerialPortInfo.availablePorts", return_value=[]):
            w.on_open_connection_settings()
        dialog = w._connection_settings
        self.assertEqual(dialog.transport_widget.port_combo.count(), 0)
        self.assertEqual(dialog.transport_widget.port_combo.currentIndex(), -1)
        self.assertEqual(dialog.transport_widget.port_combo.placeholderText(), "Select port")
        self.assertTrue(dialog.transport_widget.parity_combo.isVisible())
        dialog.capture_toggle.click()
        dialog.transport_widget.baud_combo.setCurrentText("230400")
        dialog.transport_widget.parity_combo.setCurrentIndex(dialog.transport_widget.parity_combo.findData("E"))
        dialog.log_to_file_checkbox.setChecked(False)
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(w.session.settings.transport.baudrate, 115200)
        self.assertEqual(w.session.settings.transport.parity, "N")
        self.assertTrue(w.session.settings.log_to_file)
        w.on_open_connection_settings()
        self.assertEqual(dialog.transport_widget.baud_combo.currentText(), "115200")
        dialog.transport_widget.baud_combo.showPopup()
        APP.processEvents()
        view = dialog.transport_widget.baud_combo.view()
        row_height = view.sizeHintForRow(0)
        self.assertGreaterEqual(view.viewport().height(), row_height * dialog.transport_widget.baud_combo.count())
        dialog.transport_widget.baud_combo.hidePopup()
        self.assertTrue(dialog.isVisible())
        dialog.transport_widget.parity_combo.setCurrentIndex(dialog.transport_widget.parity_combo.findData("E"))
        dialog.log_to_file_checkbox.setChecked(False)
        dialog.buttons.button(QDialogButtonBox.StandardButton.Save).click()
        self.assertEqual(w.session.settings.transport.parity, "E")
        self.assertFalse(w.session.settings.log_to_file)


if __name__ == "__main__":
    unittest.main()
