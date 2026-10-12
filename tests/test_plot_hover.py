"""Cursor coordinate tooltips without capture-history reads or drag interference."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from modules.core.plotter import Plotter
from modules.widgets.plot_widget import PlotWidget

APP = QApplication.instance() or QApplication([])


class VisibilityEvents(QObject):
    def __init__(self):
        super().__init__()
        self.shown = 0
        self.hidden = 0

    def eventFilter(self, watched, event):
        self.shown += event.type() == QEvent.Type.Show
        self.hidden += event.type() == QEvent.Type.Hide
        return False


class PlotHoverTest(unittest.TestCase):
    def setUp(self):
        self.widget = PlotWidget()
        self.widget._timer.stop()
        self.widget.resize(800, 600)
        self.addCleanup(self.widget.close)
        stores = {}
        for label, values in [('a', (0, 10)), ('b', (-10, 10))]:
            store = stores[label] = Plotter()
            for timestamp, value in zip((0, 10), values):
                store.add_sample(timestamp, value)
        self.widget.replace_series(stores, 0.)
        self.widget.show()
        APP.processEvents()
        self.widget._set_time_range(2, 8)
        self.graph = self.widget.graph
        self.graph._y_ranges['a'] = (0, 10)
        self.graph._y_ranges['b'] = (-10, 10)

    def move(self, position):
        event = QMouseEvent(QEvent.Type.MouseMove, position, self.graph.mapToGlobal(position.toPoint()),
                            Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.graph, event)

    def test_maps_both_axes_and_selects_the_hovered_signal(self):
        for row, label, expected_y in [(0, 'a', 7.5), (1, 'b', 5)]:
            # Set manual ranges to contain samples even when viewing a sparse range.
            _, plot = self.graph.panel_geometry(row)
            self.widget.set_series_style(label, 'digital')
            position = QPointF(plot.left()+plot.width()*.25, plot.top()+plot.height()*.25)
            actual_label, x, y, _ = self.graph._hover_coordinates(position)
            self.assertEqual(actual_label, label)
            self.assertAlmostEqual(x, 3.5)
            self.assertAlmostEqual(y, expected_y)

    def test_mouse_tracking_shows_tooltip_without_click_or_history_reads(self):
        self.widget._set_time_range(0, 10)
        _, plot = self.graph.panel_geometry(0)
        with patch.object(self.widget._series['a'], 'read_visible_samples', side_effect=AssertionError('hover read history')):
            self.move(plot.center())
            self.assertTrue(self.graph.hasMouseTracking())
            self.assertTrue(self.graph._hover_timer.isActive())
            self.assertTrue(self.graph._hover_tip.isVisible())
            self.assertIn('X: 5.000000 s', self.graph._hover_tip.text())
            self.assertIn('Y: 5', self.graph._hover_tip.text())
            self.assertEqual(self.widget._time_range(), (0, 10))

    def test_updates_use_current_time_and_manual_y_ranges(self):
        self.widget._set_time_range(0, 10)
        _, plot = self.graph.panel_geometry(0)
        self.move(plot.center())
        self.widget.set_series_style('a', 'digital')
        self.widget._set_time_range(2, 8)
        self.graph._y_ranges['a'] = (10, 30)
        self.graph._update_hover_tooltip()
        self.assertIn('X: 5.000000 s', self.graph._hover_tip.text())
        self.assertIn('Y: 20', self.graph._hover_tip.text())

    def test_no_tooltip_on_axes_headers_or_empty_plot(self):
        _, plot = self.graph.panel_geometry(0)
        for position in [QPointF(10, plot.center().y()), QPointF(plot.center().x(), 10), plot.center()]:
            self.move(position)
            self.assertFalse(self.graph._hover_timer.isActive())
            self.assertFalse(self.graph._hover_tip.isVisible())
        self.widget.clear_values()
        self.move(plot.center())
        self.assertFalse(self.graph._hover_tip.isVisible())

    def test_drag_leave_and_close_clear_hover(self):
        self.widget._set_time_range(0, 10)
        _, plot = self.graph.panel_geometry(0)
        self.move(plot.center())
        self.graph.begin_drag(plot.center())
        self.assertFalse(self.graph._hover_timer.isActive())
        self.assertFalse(self.graph._hover_tip.isVisible())
        self.move(plot.center()+QPointF(10, 0))
        self.assertFalse(self.graph._hover_tip.isVisible())
        self.graph.end_drag()
        for target in (self.graph.headers['a'], self.graph.mode_buttons['a'], self.graph):
            self.move(plot.center())
            event = QEvent.Type.Leave if target == self.graph else QEvent.Type.Enter
            QApplication.sendEvent(target, QEvent(event))
            self.assertFalse(self.graph._hover_timer.isActive())
            self.assertFalse(self.graph._hover_tip.isVisible())
        self.move(plot.center())
        self.widget.hide()
        self.assertFalse(self.graph._hover_tip.isVisible())

    def test_live_updates_keep_same_readout_visible_without_restarting_it(self):
        self.widget._set_time_range(0, 10)
        _, plot = self.graph.panel_geometry(0)
        tip = self.graph._hover_tip
        events = VisibilityEvents()
        tip.installEventFilter(events)
        self.move(plot.center())
        for maximum in range(11, 40):
            self.graph._y_ranges['a'] = (0, maximum)
            self.graph._update_hover_tooltip()
            APP.processEvents()
            self.assertTrue(tip.isVisible())
            self.assertIn(f'Y: {maximum/2:g}', tip.text())
        self.assertEqual(events.shown, 1)
        self.assertEqual(events.hidden, 0)
        self.assertTrue(tip.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        self.assertTrue(tip.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.graph._clear_hover()
        self.assertFalse(tip.isVisible())
        self.assertEqual(events.hidden, 1)

    def test_readout_stays_on_screen_at_bottom_right(self):
        self.widget._set_time_range(0, 10)
        _, plot = self.graph.panel_geometry(0)
        screen = QRect(0, 0, 320, 200)
        with patch('modules.widgets.plot_widget.QGuiApplication.screenAt') as screen_at, \
                patch.object(self.graph, 'mapToGlobal', return_value=screen.bottomRight()):
            screen_at.return_value.availableGeometry.return_value = screen
            self.move(plot.center())
            bounds = self.graph._hover_tip.geometry()
            self.assertTrue(screen.contains(bounds))
            self.assertLess(bounds.right(), screen.right())
            self.assertLess(bounds.bottom(), screen.bottom())


if __name__ == '__main__':
    unittest.main()
