"""Live plot widget for captured numeric values."""

from __future__ import annotations

from collections.abc import Iterable

import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QSpinBox, QVBoxLayout, QWidget

from ..core.models import CapturedValue
from ..core.plotter import Plotter


PLOT_REFRESH_INTERVAL_MS = 100


class PlotWidget(QWidget):
    def __init__(self, parent=None, time_window: float = 10.0):
        super().__init__(parent)
        self.setObjectName("LivePlot")
        self.setMinimumSize(320, 220)

        self._time_window = time_window
        self._series: dict[str, Plotter] = {}
        self._plots: dict[str, pg.PlotItem] = {}
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._series_actions: dict[str, QAction] = {}
        self._visible_labels: set[str] = set()
        self._start_time: float | None = None
        self._has_pending_refresh = False
        self._auto_scroll_enabled = True
        self._is_setting_time_range = False

        self.graph = pg.GraphicsLayoutWidget()
        self.graph.setBackground("#fbfcfc")

        bucket_count_tooltip = (
            "Maximum target number of displayed bucket groups for the visible time range. "
            "The actual displayed bucket count can be lower because PlotTTY uses fixed precomputed bucket levels. "
            "Auto uses the graph width; each displayed bucket keeps the first, last, minimum, and maximum points."
        )

        self.bucket_count = QSpinBox()
        self.bucket_count.setRange(0, 100_000)
        self.bucket_count.setValue(0)
        self.bucket_count.setSpecialValueText("Auto")
        self.bucket_count.setToolTip(bucket_count_tooltip)
        self.bucket_count.valueChanged.connect(self._refresh_visible_data)

        self.visible_points_label = QLabel("Visible points: 0")
        self.visible_points_label.setToolTip(
            "Maximum raw point count currently visible in any shown series. "
            "PlotTTY uses raw samples when this is at or below the target bucket count."
        )
        self.samples_per_bucket_label = QLabel("Samples/bucket: 0")
        self.samples_per_bucket_label.setToolTip(
            "Target raw samples per displayed bucket for the visible series with the most points. "
            "This is visible points divided by max buckets; the actual plotted bucket level may be coarser."
        )

        self.series_menu = QMenu(self)
        self.series_button = QPushButton("Series")
        self.series_button.setMenu(self.series_menu)
        self.series_button.setEnabled(False)

        self.auto_scroll_button = QPushButton("Auto Scroll")
        self.auto_scroll_button.setCheckable(True)
        self.auto_scroll_button.setChecked(True)
        self.auto_scroll_button.clicked.connect(self._toggle_auto_scroll)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addStretch()
        bucket_count_label = QLabel("Max buckets")
        bucket_count_label.setToolTip(bucket_count_tooltip)
        toolbar.addWidget(bucket_count_label)
        toolbar.addWidget(self.bucket_count)
        toolbar.addWidget(self.visible_points_label)
        toolbar.addWidget(self.samples_per_bucket_label)
        toolbar.addWidget(self.series_button)
        toolbar.addWidget(self.auto_scroll_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self.graph)

        self._timer = QTimer(self)
        self._timer.setInterval(PLOT_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh_pending_data)
        self._timer.start()

    def append_values(self, values: Iterable[CapturedValue]) -> None:
        captured_values = list(values)
        if not captured_values:
            return

        for captured in captured_values:
            if self._start_time is None:
                self._start_time = captured.timestamp

            if captured.label not in self._series:
                self._series[captured.label] = Plotter()
                self._visible_labels.add(captured.label)
                self._add_series_menu_item(captured.label)
                self._rebuild_plots()

            self._series[captured.label].add_sample(captured.timestamp - self._start_time, captured.value)
            self._has_pending_refresh = True

    def clear_values(self) -> None:
        for series in self._series.values():
            series.close()
        self._series.clear()
        self._plots.clear()
        self._curves.clear()
        self._series_actions.clear()
        self._visible_labels.clear()
        self._start_time = None
        self._has_pending_refresh = False
        self.series_menu.clear()
        self.series_button.setEnabled(False)
        self.graph.clear()
        self._toggle_auto_scroll(True)

    def _refresh_pending_data(self) -> None:
        if not self._has_pending_refresh:
            return

        self._has_pending_refresh = False
        if self._auto_scroll_enabled:
            self._show_recent_data()
        else:
            self._update_visible_curve_data()

    def _toggle_auto_scroll(self, enabled: bool) -> None:
        self._auto_scroll_enabled = enabled
        self.auto_scroll_button.setChecked(enabled)
        if enabled:
            self._show_recent_data()
        else:
            self._show_all_data()

    def _show_recent_data(self) -> None:
        latest_time = self._latest_sample_time()
        start_time = max(0.0, latest_time - self._time_window)
        end_time = max(self._time_window, latest_time)
        self._set_time_range(start_time, end_time)

    def _show_all_data(self) -> None:
        latest_time = self._latest_sample_time()
        self._set_time_range(0.0, max(self._time_window, latest_time))

    def _set_time_range(self, start_time: float, end_time: float) -> None:
        self._is_setting_time_range = True
        for plot in self._plots.values():
            plot.setXRange(start_time, end_time, padding=0)
        self._is_setting_time_range = False
        self._update_visible_curve_data(start_time, end_time)

    def _handle_x_range_changed(self, view_box=None, _range=None) -> None:
        if self._is_setting_time_range:
            return

        if self._auto_scroll_enabled:
            self._auto_scroll_enabled = False
            self.auto_scroll_button.setChecked(False)

        if view_box is not None:
            start_time, end_time = view_box.viewRange()[0]
            self._set_time_range(start_time, end_time)

    def _add_series_menu_item(self, label: str) -> None:
        action = QAction(label, self)
        action.setCheckable(True)
        action.setChecked(True)
        action.toggled.connect(lambda checked, series_label=label: self._toggle_series_visibility(series_label, checked))
        self._series_actions[label] = action
        self.series_menu.addAction(action)
        self.series_button.setEnabled(True)

    def _toggle_series_visibility(self, label: str, visible: bool) -> None:
        if visible:
            self._visible_labels.add(label)
        else:
            self._visible_labels.discard(label)

        self._rebuild_plots()
        self._has_pending_refresh = True
        self._refresh_pending_data()

    def _rebuild_plots(self) -> None:
        self.graph.clear()
        self._plots.clear()
        self._curves.clear()

        for row, label in enumerate(label for label in self._series if label in self._visible_labels):
            plot = self.graph.addPlot(row=row, col=0, title=label)
            self._configure_plot(plot)
            curve = plot.plot(pen=pg.mkPen(_color_for_index(row), width=2))
            curve.setClipToView(True)
            curve.setDownsampling(auto=True, method="peak")
            self._plots[label] = plot
            self._curves[label] = curve

        if self._auto_scroll_enabled:
            self._show_recent_data()

    def _configure_plot(self, plot: pg.PlotItem) -> None:
        plot.showGrid(x=True, y=True, alpha=0.28)
        plot.setLabel("bottom", "Time", units="s")
        plot.setLabel("left", "Value")
        plot.setMouseEnabled(x=True, y=True)
        plot.enableAutoRange(axis="x", enable=False)
        plot.enableAutoRange(axis="y", enable=True)
        plot.getViewBox().sigXRangeChanged.connect(self._handle_x_range_changed)

    def _latest_sample_time(self) -> float:
        return max(
            (timestamp for series in self._series.values() if (timestamp := series.latest_timestamp()) is not None),
            default=0.0,
        )

    def _time_range(self) -> tuple[float, float]:
        if not self._plots:
            return 0.0, self._time_window
        plot = next(iter(self._plots.values()))
        start_time, end_time = plot.viewRange()[0]
        return start_time, end_time

    def _update_visible_curve_data(self, start_time: float | None = None, end_time: float | None = None) -> None:
        if start_time is None or end_time is None:
            start_time, end_time = self._time_range()

        visible_counts = []
        samples_per_bucket_values = []
        for label, series in self._series.items():
            if label not in self._curves:
                continue

            visible_samples = series.count_visible_samples(start_time, end_time)
            bucket_count = self._bucket_count_for_series(label)
            visible_counts.append(visible_samples)
            samples_per_bucket_values.append(visible_samples / bucket_count)

            x_values, y_values = series.read_visible_samples(start_time, end_time, bucket_count)
            self._curves[label].setData(x_values, y_values)

        visible_point_count = max(visible_counts, default=0)
        self.visible_points_label.setText(f"Visible points: {visible_point_count:,}")
        samples_per_bucket = max(samples_per_bucket_values, default=0.0)
        self.samples_per_bucket_label.setText(f"Samples/bucket: {_format_samples_per_bucket(samples_per_bucket)}")

    def _refresh_visible_data(self) -> None:
        self._update_visible_curve_data()

    def _bucket_count_for_series(self, label: str) -> int:
        if self.bucket_count.value() > 0:
            return self.bucket_count.value()

        plot = self._plots.get(label)
        if plot is None:
            return 1000

        width = int(plot.getViewBox().width())
        return max(1, width)

    def closeEvent(self, event) -> None:
        for series in self._series.values():
            series.close()
        super().closeEvent(event)


def _color_for_index(index: int) -> str:
    colors = ["#1d9bd1", "#ef7d00", "#16a34a", "#dc2626", "#7c3aed", "#0f766e"]
    return colors[index % len(colors)]


def _format_samples_per_bucket(value: float) -> str:
    if value == 0:
        return "0"
    if value < 10:
        return f"{value:.1f}"
    return f"{value:,.0f}"
