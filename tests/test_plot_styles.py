"""Independent graph-type rendering and view configuration."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from qt_cleanup import delete_qt_object
import gc

import numpy as np
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from modules.core.extraction import ExtractionRule
from modules.core.series_store import SeriesStore
from modules.widgets.plot_widget import PlotWidget, _CurveData, _create_polygon, _prepare_plot_arrays

APP = QApplication.instance() or QApplication([])


class PlotStylesTest(unittest.TestCase):
    def test_polygon_owns_coordinates_after_source_arrays_are_released(self):
        for count in (0, 1, 25_001):
            with self.subTest(count=count):
                x = np.arange(count * 2, dtype='>f8')[::2]
                y = -x[::-1]
                expected = list(zip(x.tolist(), y.tolist()))
                polygon = _create_polygon(x, y)
                del x, y
                gc.collect()
                self.assertEqual([(point.x(), point.y()) for point in polygon], expected)

    def test_short_device_window_retains_raw_points_in_every_style(self):
        self.plot.clear_values()
        store = SeriesStore()
        for i in range(2000):
            store.add_sample(i / 10000, (-1) ** i * i)
        self.plot.replace_series({'a': store}, 0.)
        for style in ('lines', 'digital', 'dots'):
            self.plot.set_series_style('a', style)
            self.plot._set_time_range(0, 1999 / 10000)
            curve = self.plot._curves['a']
            np.testing.assert_array_equal(curve.xData, np.arange(2000) / 10000)
            np.testing.assert_array_equal(curve.yData, [(-1) ** i * i for i in range(2000)])
            self.assertEqual(self.plot.downsample_ratio_label.text(), 'Downsample: 1:1')

    def test_each_style_has_its_own_limit_regardless_of_series_count(self):
        for i in range(1, 10):
            store = self.plot._series[str(i)] = SeriesStore()
            store.add_sample(0, i)
        self.plot._rebuild_plots()
        limits = {'lines': 12345, 'digital': 6789, 'dots': 2345}
        for style, limit in limits.items():
            self.plot.set_raw_point_limit(style, limit)
        for style, limit in limits.items():
            self.plot.set_series_style('a', style)
            with patch.object(self.plot._series['a'], 'read_visible_samples',
                              wraps=self.plot._series['a'].read_visible_samples) as read:
                self.plot._set_time_range(0, 10)
            self.assertEqual(read.call_args.kwargs['raw_point_limit'], limit)
        self.plot.set_rules([ExtractionRule(str(i), 'first_number', visible=False) for i in range(1, 10)])
        with patch.object(self.plot._series['a'], 'read_visible_samples',
                          wraps=self.plot._series['a'].read_visible_samples) as read:
            self.plot._set_time_range(0, 10)
        self.assertEqual(read.call_args.kwargs['raw_point_limit'], limits['dots'])

    def test_changing_raw_limit_refreshes_existing_data_without_new_samples(self):
        self.plot.clear_values()
        store = SeriesStore()
        for i in range(2000):
            store.add_sample(i / 10000, (-1) ** i * i)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 1999 / 10000)
        self.plot.set_raw_point_limit('lines', 500)
        self.assertTrue(self.plot._has_pending_refresh)
        self.plot.on_refresh_pending_data()
        self.assertLess(len(self.plot._curves['a'].xData), 2000)
        self.plot.set_raw_point_limit('lines', 2000)
        self.plot.on_refresh_pending_data()
        np.testing.assert_array_equal(self.plot._curves['a'].xData, np.arange(2000) / 10000)
        self.assertEqual(store.sample_count(), 2000)

    def test_mode_switch_applies_its_limit_and_updates_diagnostics_immediately(self):
        self.plot.clear_values()
        store = SeriesStore()
        for i in range(4000):
            store.add_sample(i / 10000, i % 13)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 3999 / 10000)
        self.assertEqual(len(self.plot._curves['a'].xData), 4000)
        self.plot.set_series_style('a', 'dots')
        self.assertLess(len(self.plot._curves['a'].xData), 4000)
        self.assertNotEqual(self.plot.downsample_ratio_label.text(), 'Downsample: 1:1')
        self.plot.set_series_style('a', 'digital')
        self.assertEqual(len(self.plot._curves['a'].xData), 4000)
        self.assertEqual(self.plot.downsample_ratio_label.text(), 'Downsample: 1:1')
        self.assertEqual(store.sample_count(), 4000)

    def test_bulk_analog_and_digital_paths_keep_chunk_boundary_spikes_and_edges(self):
        x = np.arange(25_001, dtype=float) * .001
        for style in ('lines', 'digital'):
            y = np.sin(x) if style == 'lines' else np.arange(len(x)) % 2
            if style == 'lines':
                y[[9_999, 10_000, 19_999, 20_000, 25_000]] = [5, -5, 7, -7, 1]
            curve = _CurveData(QColor('green'), style)
            curve.set_data(x, y)
            self.assertEqual(curve.path.elementCount(), len(x) if style == 'lines' else 2 * len(x) - 1)
            for i in (0, 9_999, 10_000, 19_999, 20_000, 25_000):
                index = i if style == 'lines' else 2 * i
                element = curve.path.elementAt(index)
                self.assertEqual((element.x, element.y), (x[i], y[i]))
                if style == 'digital' and i:
                    before = curve.path.elementAt(index - 1)
                    self.assertEqual((before.x, before.y), (x[i], y[i - 1]))
            np.testing.assert_array_equal(curve.xData, x)
            np.testing.assert_array_equal(curve.yData, y)

    def test_bulk_digital_paths_handle_empty_single_flat_and_duplicate_times(self):
        cases = [([], [], []), ([0], [1], [(0, 1)]),
                 ([0, 1, 2], [3, 3, 3], [(0, 3), (1, 3), (2, 3)]),
                 ([0, 0, 1], [0, 1, 1], [(0, 0), (0, 1), (1, 1)]),
                 ([0, 4, 8], [0, 1, 0], [(0, 0), (4, 0), (4, 1), (8, 1), (8, 0)])]
        for x, y, expected in cases:
            with self.subTest(x=x, y=y):
                curve = _CurveData(QColor('green'), 'digital')
                curve.set_data(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
                actual = [(curve.path.elementAt(i).x, curve.path.elementAt(i).y)
                          for i in range(curve.path.elementCount())]
                self.assertEqual(actual, expected)

    def test_bulk_dots_draw_interior_samples_without_connecting_lines(self):
        store = SeriesStore()
        for timestamp in (0, 4, 8):
            store.add_sample(timestamp, 1)
        self.plot.replace_series({'a': store}, 0.)
        self.plot.set_series_style('a', 'dots')
        self.plot._set_time_range(0, 10)
        image = self.plot.graph.grab().toImage()
        for timestamp in (0, 4, 8):
            self.assertTrue(self.has_curve_color(image, self.sample_pixel(timestamp)))
        for timestamp in (2, 6):
            self.assertFalse(self.has_curve_color(image, self.sample_pixel(timestamp)))

    def test_numeric_preparation_keeps_pairs_filters_nonfinite_and_handles_views(self):
        x = np.arange(12, dtype=float)[::2]
        y = np.arange(12, dtype=float)[1::2]
        actual_x, actual_y = _prepare_plot_arrays(x, y)
        np.testing.assert_array_equal(actual_x, x)
        np.testing.assert_array_equal(actual_y, y)
        self.assertTrue(actual_x.flags.c_contiguous and actual_y.flags.c_contiguous)
        actual_x, actual_y = _prepare_plot_arrays([0, np.nan, 2, 3, 4], [5, 6, np.inf, 8])
        np.testing.assert_array_equal(actual_x, [0, 3])
        np.testing.assert_array_equal(actual_y, [5, 8])
        for x, y in [([], []), ([np.nan], [0]), ([0], [])]:
            actual_x, actual_y = _prepare_plot_arrays(x, y)
            self.assertEqual(len(actual_x), 0)
            self.assertEqual(len(actual_y), 0)

    def choose_mode(self, label, mode):
        button = self.plot.graph.mode_buttons[label]
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(button.picker.options[mode], Qt.MouseButton.LeftButton)

    def setUp(self):
        self.plot = PlotWidget()
        self.addCleanup(delete_qt_object, self.plot)
        self.addCleanup(self.plot.close)
        self.plot._timer.stop()
        self.plot.resize(800, 500)
        store = SeriesStore()
        store.add_sample(0, 1)
        store.add_sample(8, 1)
        self.plot.replace_series({'a': store}, 0.)
        self.plot.show()
        APP.processEvents()
        self.plot._set_time_range(0, 10)

    def sample_pixel(self, timestamp):
        _panel, panel = self.plot.graph.panel_geometry(0)
        minimum, maximum = self.plot.graph._y_range('a')
        start, end = self.plot.graph.time_range
        return (round(panel.left() + (timestamp - start) / (end - start) * panel.width()),
                round(panel.bottom() - (1 - minimum) / (maximum - minimum) * panel.height()))

    def has_curve_color(self, image, point):
        x, y = point
        # The first series is green; include translucent/antialiased marker pixels.
        return any(color.green() > color.blue() + 5 and color.green() > color.red() + 10
                   for px in range(x - 2, x + 3) for py in range(y - 2, y + 3)
                   if (color := image.pixelColor(px, py)))

    def test_dot_size_stays_small_when_zooming_value_axis(self):
        self.plot.set_series_style('a', 'dots')
        x, y = self.sample_pixel(8)
        for span in (1, .001):
            self.plot.graph._y_ranges['a'] = (1 - span / 2, 1 + span / 2)
            image = self.plot.graph.grab().toImage()
            pixels = [(px, py) for px in range(x - 8, x + 9) for py in range(y - 8, y + 9)
                      if (color := image.pixelColor(px, py)).green() > color.blue() + 5
                      and color.green() > color.red() + 10]
            self.assertTrue(pixels)
            self.assertLessEqual(max(px for px, py in pixels) - min(px for px, py in pixels), 3)
            self.assertLessEqual(max(py for px, py in pixels) - min(py for px, py in pixels), 3)

    def test_dots_have_samples_without_connecting_strokes(self):
        graph = self.plot.graph
        middle = self.sample_pixel(4)
        endpoint = self.sample_pixel(8)
        self.assertTrue(self.has_curve_color(graph.grab().toImage(), middle))
        self.choose_mode('a', 'dots')
        image = graph.grab().toImage()
        self.assertTrue(self.has_curve_color(image, endpoint))
        self.assertFalse(self.has_curve_color(image, middle))
        self.choose_mode('a', 'lines')
        image = graph.grab().toImage()
        self.assertTrue(self.has_curve_color(image, middle))
        self.assertTrue(self.has_curve_color(image, endpoint))

    def test_single_sample_is_visible_in_dot_modes(self):
        self.plot.clear_values()
        store = SeriesStore()
        store.add_sample(0, 1)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 10)
        self.plot.set_series_style('a', 'dots')
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.sample_pixel(0)))

    def test_switch_is_per_series_and_uses_cached_data(self):
        self.plot.set_raw_point_limit('dots', self.plot.raw_point_limits['lines'])
        self.plot.set_raw_point_limit('digital', self.plot.raw_point_limits['lines'])
        self.plot._series['b'] = SeriesStore()
        self.plot._series['b'].add_sample(9, 2)
        self.plot._rebuild_plots()
        self.plot._set_time_range(0, 10)
        with patch.object(self.plot._series['a'], 'read_visible_samples',
                          side_effect=AssertionError('mode switch must not read history')):
            self.plot.set_series_style('a', 'digital')
            self.plot.set_series_style('a', 'dots')
        self.assertEqual(self.plot._curves['b'].style, 'lines')
        self.assertEqual(self.plot._series['a'].sample_count(), 2)
        self.assertEqual(self.plot.graph.mode_buttons['a'].mode, 'dots')

    def value_pixel(self, timestamp, value):
        _panel, panel = self.plot.graph.panel_geometry(0)
        minimum, maximum = self.plot.graph._y_range('a')
        start, end = self.plot.graph.time_range
        return (round(panel.left() + (timestamp-start)/(end-start)*panel.width()),
                round(panel.bottom() - (value-minimum)/(maximum-minimum)*panel.height()))

    def test_digital_holds_previous_value_and_changes_at_sample_time(self):
        self.plot.clear_values()
        store = SeriesStore()
        for timestamp, value in [(0, 0), (4, 1), (8, 0)]:
            store.add_sample(timestamp, value)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 10)
        button = self.plot.graph.mode_buttons['a']
        self.assertEqual(button.text(), 'Mode: Analog')
        image = self.plot.graph.grab().toImage()
        self.assertTrue(self.has_curve_color(image, self.value_pixel(2, .5)))
        self.choose_mode('a', 'digital')
        image = self.plot.graph.grab().toImage()
        self.assertTrue(self.has_curve_color(image, self.value_pixel(2, 0)))
        self.assertTrue(self.has_curve_color(image, self.value_pixel(4, .5)))
        self.assertTrue(self.has_curve_color(image, self.value_pixel(6, 1)))
        self.assertTrue(self.has_curve_color(image, self.value_pixel(8, .5)))
        self.assertFalse(self.has_curve_color(image, self.value_pixel(2, .5)))
        self.assertFalse(self.has_curve_color(image, self.value_pixel(6, .5)))
        self.assertEqual(store.sample_count(), 3)
        self.choose_mode('a', 'lines')
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.value_pixel(2, .5)))

    def test_digital_sparse_range_holds_value_between_samples(self):
        self.plot.set_series_style('a', 'digital')
        self.plot._set_time_range(2, 6)
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.sample_pixel(4)))
        # Every style retains the same boundary samples inside a sparse gap.
        self.plot.set_series_style('a', 'lines')
        self.assertEqual(len(self.plot._curves['a'].xData), 2)
        self.plot.set_series_style('a', 'digital')
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.sample_pixel(4)))

    def test_boundary_context_connects_analog_and_digital_but_does_not_invent_dots(self):
        self.plot.clear_values()
        store = SeriesStore()
        for timestamp, value in [(0, 0), (4, 1), (8, 0)]:
            store.add_sample(timestamp, value)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(1, 3)
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.value_pixel(2, .5)))
        self.plot.set_series_style('a', 'digital')
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.value_pixel(2, 0)))
        self.plot.set_series_style('a', 'dots')
        image = self.plot.graph.grab().toImage()
        self.assertFalse(self.has_curve_color(image, self.value_pixel(2, .5)))
        self.assertFalse(self.has_curve_color(image, self.value_pixel(2, 0)))
        self.assertEqual(self.plot.visible_points_label.text(), 'Points: 0')
        self.assertEqual(self.plot.downsample_ratio_label.text(), 'Downsample: 1:1')

    def test_digital_single_sample_remains_visible(self):
        self.plot.clear_values()
        store = SeriesStore()
        store.add_sample(0, 1)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 10)
        self.plot.set_series_style('a', 'digital')
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.sample_pixel(0)))

    def test_digital_steps_support_multilevel_values_and_equal_timestamps(self):
        self.plot.clear_values()
        store = SeriesStore()
        for timestamp, value in [(0, 2), (4, 5), (4, 3), (8, -1)]:
            store.add_sample(timestamp, value)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 10)
        self.plot.set_series_style('a', 'digital')
        path = self.plot._curves['a'].path
        self.assertEqual([(path.elementAt(i).x, path.elementAt(i).y) for i in range(path.elementCount())],
                         [(0, 2), (4, 2), (4, 5), (4, 3), (8, 3), (8, -1)])

    def test_digital_choice_survives_rule_visibility_and_rename(self):
        self.plot.set_series_style('a', 'digital')
        self.plot.set_rules([ExtractionRule('a', 'first_number', visible=False)])
        self.plot.set_rules([ExtractionRule('a', 'first_number')])
        self.plot.update_series_labels({'a': 'renamed'})
        self.assertEqual(self.plot.graph.mode_buttons['renamed'].mode, 'digital')

    def test_style_survives_visibility_rules_rename_and_new_samples(self):
        self.plot.set_series_style('a', 'dots')
        self.plot.set_rules([ExtractionRule('a', 'first_number', visible=False)])
        self.assertNotIn('a', self.plot.graph.mode_buttons)
        self.plot.set_rules([ExtractionRule('a', 'first_number')])
        self.assertEqual(self.plot.graph.mode_buttons['a'].mode, 'dots')
        self.plot.update_series_labels({'a': 'renamed'})
        self.plot._series['renamed'].add_sample(9, 2)
        self.plot._set_time_range(0, 10)
        self.assertEqual(self.plot.graph.mode_buttons['renamed'].mode, 'dots')
        self.assertEqual(self.plot._series['renamed'].sample_count(), 3)
        self.plot.clear_values()
        store = SeriesStore()
        store.add_sample(0, 3)
        self.plot.replace_series({'renamed': store}, 0.)
        self.assertEqual(self.plot.graph.mode_buttons['renamed'].mode, 'lines')



    def test_picker_keyboard_selection_and_escape_preserve_other_series(self):
        self.plot._series['b'] = SeriesStore()
        self.plot._series['b'].add_sample(9, 2)
        self.plot._rebuild_plots()
        button = self.plot.graph.mode_buttons['a']
        self.assertFalse(button.icon().isNull())
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertTrue(button.picker.isVisible())
        self.assertTrue(button.picker.options['lines'].isChecked())
        QTest.keyClick(button.picker.options['lines'], Qt.Key.Key_Down)
        QTest.keyClick(button.picker.options['digital'], Qt.Key.Key_Return)
        self.assertFalse(button.picker.isVisible())
        self.assertEqual(button.mode, 'digital')
        self.assertEqual(self.plot.graph.mode_buttons['b'].mode, 'lines')
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertTrue(button.picker.options['digital'].isChecked())
        QTest.keyClick(button.picker.options['digital'], Qt.Key.Key_Down)
        QTest.keyClick(button.picker.options['dots'], Qt.Key.Key_Escape)
        self.assertFalse(button.picker.isVisible())
        self.assertEqual(button.mode, 'digital')

    def test_badge_tracks_title_width_and_elides_long_names(self):
        self.plot.update_series_labels({'a': 'A very long signal name ' * 8})
        label = next(iter(self.plot.graph.headers))
        header = self.plot.graph.headers[label]
        button = self.plot.graph.mode_buttons[label]
        self.assertGreater(button.x(), header.geometry().right())
        self.assertLess(button.geometry().right(), self.plot.graph.width()-40)
        self.assertIn(label, button.accessibleName())
        self.assertEqual(header.toolTip(), label)

    def test_styled_picker_keeps_descriptions_visible(self):
        from mainwindow import apply_application_style
        apply_application_style(APP)
        self.addCleanup(lambda: APP.setStyleSheet(''))
        button = self.plot.graph.mode_buttons['a']
        self.plot.set_series_style('a', 'digital')
        button.click()
        APP.processEvents()
        for mode, option in button.picker.options.items():
            self.assertGreaterEqual(option.height(), 58)
            self.assertEqual(option.title.property('selected'), mode == 'digital')
            self.assertEqual(option.checkmark.isVisible(), mode == 'digital')
            description = option.findChild(type(option.title), 'PlotModeDescription')
            self.assertGreaterEqual(description.height(), description.fontMetrics().height())
        button.picker.reject()


if __name__ == '__main__':
    unittest.main()
