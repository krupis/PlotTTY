"""Independent graph-type rendering and view configuration."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from modules.core.extraction import ExtractionRule
from modules.core.plotter import Plotter
from modules.widgets.plot_widget import PlotWidget

APP = QApplication.instance() or QApplication([])


class PlotStylesTest(unittest.TestCase):
    def setUp(self):
        self.plot = PlotWidget()
        self.addCleanup(self.plot.close)
        self.plot._timer.stop()
        self.plot.resize(800, 500)
        store = Plotter()
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
        selector = graph.style_selectors['a']
        selector.setCurrentIndex(selector.findData('dots'))
        image = graph.grab().toImage()
        self.assertTrue(self.has_curve_color(image, endpoint))
        self.assertFalse(self.has_curve_color(image, middle))
        selector.setCurrentIndex(selector.findData('lines'))
        image = graph.grab().toImage()
        self.assertTrue(self.has_curve_color(image, middle))
        self.assertTrue(self.has_curve_color(image, endpoint))

    def test_single_sample_is_visible_in_dot_modes(self):
        self.plot.clear_values()
        store = Plotter()
        store.add_sample(0, 1)
        self.plot.replace_series({'a': store}, 0.)
        self.plot._set_time_range(0, 10)
        self.plot.set_series_style('a', 'dots')
        self.assertTrue(self.has_curve_color(self.plot.graph.grab().toImage(), self.sample_pixel(0)))

    def test_switch_is_per_series_and_uses_cached_data(self):
        self.plot._series['b'] = Plotter()
        self.plot._series['b'].add_sample(9, 2)
        self.plot._rebuild_plots()
        self.plot._set_time_range(0, 10)
        with patch.object(self.plot._series['a'], 'read_visible_samples',
                          side_effect=AssertionError('mode switch must not read history')):
            self.plot.set_series_style('a', 'dots')
        self.assertEqual(self.plot._curves['b'].style, 'lines')
        self.assertEqual(self.plot._series['a'].sample_count(), 2)
        self.assertEqual(self.plot.graph.style_selectors['a'].currentData(), 'dots')

    def test_style_survives_visibility_rules_rename_and_new_samples(self):
        self.plot.set_series_style('a', 'dots')
        self.plot.set_rules([ExtractionRule('a', 'first_number', visible=False)])
        self.assertNotIn('a', self.plot.graph.style_selectors)
        self.plot.set_rules([ExtractionRule('a', 'first_number')])
        self.assertEqual(self.plot.graph.style_selectors['a'].currentData(), 'dots')
        self.plot.update_series_labels({'a': 'renamed'})
        self.plot._series['renamed'].add_sample(9, 2)
        self.plot._set_time_range(0, 10)
        self.assertEqual(self.plot.graph.style_selectors['renamed'].currentData(), 'dots')
        self.assertEqual(self.plot._series['renamed'].sample_count(), 3)
        self.plot.clear_values()
        store = Plotter()
        store.add_sample(0, 3)
        self.plot.replace_series({'renamed': store}, 0.)
        self.assertEqual(self.plot.graph.style_selectors['renamed'].currentData(), 'lines')



if __name__ == '__main__':
    unittest.main()
