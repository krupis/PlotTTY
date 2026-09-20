"""Live plot widget for captured numeric values."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget

from ..core.models import CapturedValue
from ..core.plotter import Plotter


PLOT_REFRESH_INTERVAL_MS = 50
PLOT_BACKGROUND = "#1f2328"
PLOT_AXIS = "#5c6370"
PLOT_TEXT = "#dce3ea"
AUTO_SCROLL_TOOLTIP = "Keep the plot view following the newest incoming data."
SHOW_ALL_TOOLTIP = "Zoom the plot out to show all captured data."

class PlotWidget(QWidget):
    def __init__(self, parent=None, time_window: float = 10.0):
        super().__init__(parent)
        self.setObjectName("LivePlot")
        self.setMinimumSize(320, 220)

        self._time_window = time_window
        self._series: dict[str, Plotter] = {}
        self._plots: dict[str, pg.PlotItem] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._visible_labels: set[str] = set()
        self._start_time: float | None = None
        self._has_pending_refresh = False
        self._is_setting_time_range = False

        self.graph = pg.GraphicsLayoutWidget()
        self.graph.setBackground(PLOT_BACKGROUND)

        self.visible_points_label = QLabel("Points: 0")
        self.visible_points_label.setToolTip(
            "Maximum number of data points currently visible in any shown series."
        )
        self.downsample_ratio_label = QLabel("Downsample: 1:1")
        self.downsample_ratio_label.setToolTip(
            "Raw visible points compared to points sent to the plot. 1:1 means every visible point is drawn."
        )

        self.series_menu = QMenu(self)
        self.series_button = QPushButton("Series")
        self.series_button.setMenu(self.series_menu)
        self.series_button.setEnabled(False)

        self.auto_scroll_button = QPushButton("Auto Scroll")
        self.auto_scroll_button.setObjectName("PlotModeButton")
        self.auto_scroll_button.setCheckable(True)
        self.auto_scroll_button.setChecked(True)
        self.auto_scroll_button.setToolTip(AUTO_SCROLL_TOOLTIP)
        self.auto_scroll_button.clicked.connect(self.on_toggle_auto_scroll)

        self.show_all_button = QPushButton("See all plot")
        self.show_all_button.setObjectName("PlotModeButton")
        self.show_all_button.setCheckable(True)
        self.show_all_button.setToolTip(SHOW_ALL_TOOLTIP)
        self.show_all_button.clicked.connect(self.on_toggle_show_all)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addStretch()
        toolbar.addWidget(self.visible_points_label)
        toolbar.addWidget(self.downsample_ratio_label)
        toolbar.addWidget(self.series_button)
        toolbar.addWidget(self.show_all_button)
        toolbar.addWidget(self.auto_scroll_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self.graph)

        self._timer = QTimer(self)
        self._timer.setInterval(PLOT_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.on_refresh_pending_data)
        self._timer.start()

    @Slot(list)
    def append_values(self, values: Iterable[CapturedValue]) -> None:
        added_series = False
        for captured in values:
            if self._start_time is None:
                self._start_time = captured.timestamp

            if captured.label not in self._series:
                self._series[captured.label] = Plotter()
                self._visible_labels.add(captured.label)
                self._add_series_menu_item(captured.label)
                added_series = True

            self._series[captured.label].add_sample(captured.timestamp - self._start_time, captured.value)
            self._has_pending_refresh = True

        if added_series:
            self._rebuild_plots()

    def clear_values(self) -> None:
        for series in self._series.values():
            series.close()
        self._series.clear()
        self._plots.clear()
        self._curves.clear()
        self._visible_labels.clear()
        self._start_time = None
        self._has_pending_refresh = False
        self.series_menu.clear()
        self.series_button.setEnabled(False)
        self.graph.clear()
        self.on_toggle_auto_scroll(True)

    # This method is called periodically to refresh the plot with any new data that has been added since the last refresh.
    @Slot()
    def on_refresh_pending_data(self) -> None:
        if not self._has_pending_refresh:
            return

        self._has_pending_refresh = False
        if self.auto_scroll_button.isChecked():
            self.show_recent_data()
        elif self.show_all_button.isChecked():
            self.show_all_data()
        else:
            self._update_visible_curve_data()

    @Slot(bool)
    def on_toggle_auto_scroll(self, enabled: bool) -> None:
        self.auto_scroll_button.setChecked(enabled)
        if enabled:
            self.show_all_button.setChecked(False)
            self.show_recent_data()

    @Slot(bool)
    def on_toggle_show_all(self, enabled: bool) -> None:
        self.show_all_button.setChecked(enabled)
        if enabled:
            self.auto_scroll_button.setChecked(False)
            self.show_all_data()

    def show_recent_data(self) -> None:
        latest_time = self._latest_sample_time()
        start_time = max(0.0, latest_time - self._time_window)
        end_time = max(self._time_window, latest_time)
        self._set_time_range(start_time, end_time)

    def show_all_data(self) -> None:
        latest_time = self._latest_sample_time()
        self._set_time_range(0.0, max(self._time_window, latest_time))

    def _set_time_range(self, start_time: float, end_time: float) -> None:
        self._is_setting_time_range = True
        for plot in self._plots.values():
            plot.setXRange(start_time, end_time, padding=0)
        self._is_setting_time_range = False
        self._update_visible_curve_data(start_time, end_time)

    @Slot(object, object)
    def on_x_range_changed(self, view_box=None, _range=None) -> None:
        if self._is_setting_time_range:
            return

        self.auto_scroll_button.setChecked(False)
        self.show_all_button.setChecked(False)

        if view_box is not None:
            start_time, end_time = view_box.viewRange()[0]
            self._set_time_range(start_time, end_time)

    def _add_series_menu_item(self, label: str) -> None:
        action = QAction(label, self)
        action.setCheckable(True)
        action.setChecked(True)
        action.setData(label)
        action.toggled.connect(self.on_series_visibility_toggled)
        self.series_menu.addAction(action)
        self.series_button.setEnabled(True)

    @Slot(bool)
    def on_series_visibility_toggled(self, visible: bool) -> None:
        action = self.sender()
        if not isinstance(action, QAction):
            return

        label = str(action.data() or "")
        if not label:
            return

        self._set_series_visibility(label, visible)

    def _set_series_visibility(self, label: str, visible: bool) -> None:
        if visible:
            self._visible_labels.add(label)
        else:
            self._visible_labels.discard(label)

        self._rebuild_plots()
        self._has_pending_refresh = True

    def _rebuild_plots(self) -> None:
        """Recreate the visible plot layout; the timer refreshes its data."""
        self.graph.clear()
        self._plots.clear()
        self._curves.clear()

        for row, label in enumerate(label for label in self._series if label in self._visible_labels):
            plot = self.graph.addPlot(row=row, col=0, title=label)
            self._configure_plot(plot, label)
            curve = plot.plot(pen=pg.mkPen(_color_for_index(row), width=1))
            # Storage already reduces the visible range to a display-sized array.
            curve.setDownsampling(auto=False)
            self._plots[label] = plot
            self._curves[label] = curve

    def _configure_plot(self, plot: pg.PlotItem, title: str) -> None:
        axis_pen = pg.mkPen(PLOT_AXIS)
        plot.setTitle(title, color=PLOT_TEXT, size="10pt")
        plot.showGrid(x=True, y=True, alpha=0.22)
        plot.setLabel("bottom", "Time", units="s")
        plot.setLabel("left", "Value")
        bottom_axis = plot.getAxis("bottom")
        bottom_axis.setPen(axis_pen)
        bottom_axis.enableAutoSIPrefix(False)
        plot.getAxis("left").setPen(axis_pen)
        bottom_axis.setTextPen(PLOT_TEXT)
        plot.getAxis("left").setTextPen(PLOT_TEXT)
        # Dense minor grids are expensive to repaint across multiple panels.
        bottom_axis.setStyle(maxTickLevel=0)
        plot.getAxis("left").setStyle(maxTickLevel=0)
        plot.setMouseEnabled(x=True, y=True)
        plot.enableAutoRange(axis="x", enable=False)
        plot.enableAutoRange(axis="y", enable=True)
        plot.getViewBox().setBackgroundColor(PLOT_BACKGROUND)
        plot.getViewBox().sigXRangeChanged.connect(self.on_x_range_changed)

    def _latest_sample_time(self) -> float:
        latest_time = None
        for series in self._series.values():
            timestamp = series.latest_timestamp()
            if timestamp is None:
                continue
            if latest_time is None or timestamp > latest_time:
                latest_time = timestamp

        return latest_time if latest_time is not None else 0.0

    def _time_range(self) -> tuple[float, float]:
        if not self._plots:
            return 0.0, self._time_window
        plot = next(iter(self._plots.values()))
        start_time, end_time = plot.viewRange()[0]
        return start_time, end_time

    # This method updates the data for all visible curves based on the current time range.
    def _update_visible_curve_data(self, start_time: float | None = None, end_time: float | None = None) -> None:
        if start_time is None or end_time is None:
            start_time, end_time = self._time_range()

        visible_counts = []
        downsample_ratios = []
        for label, curve in self._curves.items():
            series = self._series[label]
            visible_samples, x_values, y_values = series.read_visible_samples(
                start_time,
                end_time,
                self._bucket_count_for_series(label),
            )
            x_values, y_values = _prepare_plot_arrays(x_values, y_values)
            visible_counts.append(visible_samples)
            curve.setData(x=x_values, y=y_values, connect="all", skipFiniteCheck=True)
            downsample_ratios.append(_downsample_ratio(visible_samples, len(x_values)))

        visible_point_count = max(visible_counts, default=0)
        self.visible_points_label.setText(f"Points: {visible_point_count:,}")
        self.downsample_ratio_label.setText(f"Downsample: {_format_downsample_ratio(max(downsample_ratios, default=1.0))}")

    def _bucket_count_for_series(self, label: str) -> int:
        plot = self._plots.get(label)
        if plot is None:
            return 1000

        width = int(plot.getViewBox().width())
        # Each bucket emits up to four points: first, minimum, maximum and last.
        return max(1, width // 4)

    def closeEvent(self, event) -> None:
        for series in self._series.values():
            series.close()
        super().closeEvent(event)


def _color_for_index(index: int) -> str:
    colors = ["#7cd1a8", "#89b4fa", "#f9c74f", "#f7768e", "#cba6f7", "#4dd0e1"]
    return colors[index % len(colors)]


def _prepare_plot_arrays(x_values: list[float], y_values: list[float]) -> tuple[np.ndarray, np.ndarray]:
    x_array = np.asarray(x_values, dtype=np.float64)
    y_array = np.asarray(y_values, dtype=np.float64)
    if x_array.size == 0 or y_array.size == 0:
        return x_array, y_array

    finite_mask = np.isfinite(x_array) & np.isfinite(y_array)
    if finite_mask.all():
        return x_array, y_array

    return x_array[finite_mask], y_array[finite_mask]


def _downsample_ratio(raw_point_count: int, plotted_point_count: int) -> float:
    if raw_point_count <= 0 or plotted_point_count <= 0:
        return 1.0
    return max(1.0, raw_point_count / plotted_point_count)


def _format_downsample_ratio(value: float) -> str:
    if value <= 1:
        return "1:1"
    if value < 10:
        return f"{value:.1f}:1"
    return f"{value:,.0f}:1"
