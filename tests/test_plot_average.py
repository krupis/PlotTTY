"""Range selection uses raw captured samples without blocking plot navigation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from qt_cleanup import delete_qt_object
from modules.core.extraction import CapturedValue, ExtractionRule
from modules.core.series_store import SeriesStore
from modules.widgets.plot_widget import PlotWidget

APP = QApplication.instance() or QApplication([])


class PlotAverageTest(unittest.TestCase):
    def setUp(self):
        self.widget = PlotWidget()
        self.addCleanup(delete_qt_object, self.widget)
        self.addCleanup(self.widget.close)
        self.widget._timer.stop()
        self.widget.resize(1000, 900)
        stores = {}
        for label, multiplier in (("a", 1), ("b", 10)):
            store = stores[label] = SeriesStore()
            for i in range(11):
                store.add_sample(i, i * multiplier)
        self.widget.replace_series(stores, 0.)
        self.widget.show()
        APP.processEvents()
        self.graph = self.widget.graph

    def point(self, fraction, row=0):
        _, plot = self.graph.panel_geometry(row)
        return QPointF(plot.left() + plot.width() * fraction, plot.center().y())

    def send(self, kind, point, button=Qt.MouseButton.LeftButton, modifiers=Qt.KeyboardModifier.NoModifier):
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else button
        button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else button
        QApplication.sendEvent(self.graph, QMouseEvent(
            kind, point, self.graph.mapToGlobal(point.toPoint()), button, buttons,
            modifiers))

    def select(self, start=.15, end=.85, row=0):
        self.send(QEvent.Type.MouseButtonPress, self.point(start, row))
        self.send(QEvent.Type.MouseMove, self.point(end, row))
        self.send(QEvent.Type.MouseButtonRelease, self.point(end, row))

    def finish(self):
        for _ in range(100):
            if not self.widget._average_timer.isActive():
                return
            self.widget._advance_average()
        self.fail("Average did not finish")

    def test_drag_selects_clicked_signal_without_panning_and_reports_average(self):
        self.select(row=1)
        self.assertEqual(self.widget._time_range(), (0, 10))
        self.assertFalse(self.widget.fit_capture_button.isChecked())
        self.assertEqual(self.graph._selection, ("b", 1.5, 8.5))
        self.assertTrue(self.widget._average_timer.isActive())
        self.finish()
        self.assertIn("b · 1.5–8.5 s", self.graph.selection_text)
        self.assertIn("Average: 50 · 7 samples", self.graph.selection_text)
        self.assertFalse(self.graph._hover_tip.isVisible())

    def test_reverse_drag_and_clamping_outside_canvas(self):
        self.select(.85, -.5)
        self.assertEqual(self.graph._selection, ("a", 0, 8.5))
        self.finish()
        self.assertIn("Average: 4 · 9 samples", self.graph.selection_text)

    def test_average_uses_raw_samples_independent_of_style_and_display_buckets(self):
        store = SeriesStore()
        self.addCleanup(store.close)
        for i in range(10_000):
            store.add_sample(i * .001, 100 if i % 100 == 0 else 0)
        self.widget.replace_series({"a": store}, 0.)
        for style in ("lines", "digital", "dots"):
            with self.subTest(style=style):
                self.widget.set_raw_point_limit(style, 1)
                self.widget.set_series_style("a", style)
                self.widget._set_time_range(0, 10)
                self.assertLess(len(self.widget._curves["a"].yData), 10_000)
                self.widget._calculate_average("a", 0, 10)
                self.finish()
                self.assertIn("Average: 1 · 10,000 samples", self.graph.selection_text)

    def test_selection_is_inclusive_and_does_not_include_drawing_neighbors(self):
        self.widget._calculate_average("a", 2, 4)
        self.finish()
        self.assertIn("Average: 3 · 3 samples", self.graph.selection_text)

    def test_sparse_range_and_nonfinite_samples(self):
        self.widget._calculate_average("a", 2.1, 2.9)
        self.finish()
        self.assertIn("No finite samples", self.graph.selection_text)
        store = self.widget._series["a"]
        for i, value in enumerate((float("nan"), float("inf"), -float("inf"), 16), 11):
            store.add_sample(i, value)
        self.widget._calculate_average("a", 11, 14)
        self.finish()
        self.assertIn("Average: 16 · 1 sample", self.graph.selection_text)
        self.assertIn("3 non-finite skipped", self.graph.selection_text)

    def test_large_selection_yields_and_can_be_cancelled_before_reading(self):
        with patch.object(self.widget._series["a"], "_read_raw_samples_by_index",
                          side_effect=AssertionError("Read after cancellation")):
            self.widget._calculate_average("a", 0, 10)
            self.assertIn("Calculating", self.graph.selection_text)
            self.widget.clear_selection()
            APP.processEvents()
        self.assertIsNone(self.widget._average_job)
        self.assertIsNone(self.graph._selection)
        self.assertEqual(self.graph.selection_text, "")

    def test_calculation_reads_one_bounded_chunk_per_timer_tick(self):
        import numpy as np
        reads = []

        def chunks():
            for values in (np.ones(65_536), np.full(65_536, 3.), np.full(5, 2.)):
                reads.append(len(values))
                yield values

        with patch.object(self.widget._series["a"], "iter_range_values", return_value=chunks()):
            self.widget._calculate_average("a", 0, 10)
        self.widget._advance_average()
        self.assertTrue(self.widget._average_timer.isActive())
        self.assertEqual(reads, [65_536])
        self.assertIn("Calculating", self.graph.selection_text)
        self.finish()
        self.assertIn("Average: 2 · 131,077 samples", self.graph.selection_text)

    def test_escape_clears_selection_and_allows_a_new_selection(self):
        self.select()
        QTest.keyClick(self.graph, Qt.Key.Key_Escape)
        self.assertIsNone(self.graph._selection)
        self.assertFalse(self.widget._average_timer.isActive())
        self.select(.5, .3)
        self.assertIsNotNone(self.graph._selection)

    def test_middle_drag_and_shift_left_drag_pan_without_selecting(self):
        for button, modifiers in (
            (Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.NoModifier),
            (Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier),
        ):
            with self.subTest(button=button, modifiers=modifiers):
                self.widget._set_time_range(0, 10)
                self.send(QEvent.Type.MouseButtonPress, self.point(.5), button, modifiers)
                self.send(QEvent.Type.MouseMove, self.point(.3), button, modifiers)
                self.send(QEvent.Type.MouseButtonRelease, self.point(.3), button, modifiers)
                self.assertGreater(self.widget._time_range()[0], 0)
                self.assertIsNone(self.graph._selection)
                self.assertFalse(self.widget._average_timer.isActive())

    def test_short_click_does_not_start_calculation(self):
        self.select(.5, .5)
        self.assertIsNone(self.graph._selection)
        self.assertFalse(self.widget._average_timer.isActive())

    def test_first_drag_does_not_move_the_plot_until_release(self):
        start = self.point(.15)
        end = self.point(.85)
        geometry = self.graph.geometry()
        self.send(QEvent.Type.MouseButtonPress, start)
        self.send(QEvent.Type.MouseMove, end)
        APP.processEvents()
        self.assertIn("Release", self.graph.selection_text)
        self.assertEqual(self.graph.geometry(), geometry)
        self.send(QEvent.Type.MouseButtonRelease, end)
        APP.processEvents()
        self.assertTrue(self.graph.selection_text)

    def test_hiding_during_a_drag_cancels_selection(self):
        self.send(QEvent.Type.MouseButtonPress, self.point(.15))
        self.send(QEvent.Type.MouseMove, self.point(.85))
        self.widget.hide()
        APP.processEvents()
        self.assertIsNone(self.graph._selection)
        self.assertFalse(self.widget._average_timer.isActive())
        self.assertEqual(self.graph.selection_text, "")

    def test_new_selection_replaces_pending_calculation(self):
        self.select(row=0)
        self.select(row=1)
        self.finish()
        self.assertIn("Average: 50", self.graph.selection_text)

    def test_clearing_or_replacing_capture_cancels_pending_work(self):
        self.select()
        self.widget.replace_series({}, None)
        APP.processEvents()
        self.assertIsNone(self.graph._selection)
        self.assertFalse(self.widget._average_timer.isActive())

    def test_hiding_selected_series_clears_measurement(self):
        self.select()
        self.widget.set_rules([ExtractionRule("a", "first_number", visible=False)])
        self.assertIsNone(self.graph._selection)
        self.assertFalse(self.widget._average_timer.isActive())

    def test_capture_continues_but_snapshot_is_stable(self):
        self.select()
        self.widget.append_values([CapturedValue(11, "a", 1000)])
        self.finish()
        self.assertIn("Average: 5 · 7 samples", self.graph.selection_text)

    def test_read_failure_stops_timer_and_shows_error(self):
        self.widget._calculate_average("a", 0, 10)
        with patch.object(self.widget._series["a"], "_read_raw_samples_by_index",
                          side_effect=OSError("test read failure")):
            self.widget._advance_average()
        self.assertFalse(self.widget._average_timer.isActive())
        self.assertIn("Average unavailable", self.graph.selection_text)
