"""Live plot widget rendered directly with QPainter."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import math

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QMouseEvent, QPainter, QPainterPath, QPen, QTransform, QWheelEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget

from ..core.models import CapturedValue
from ..core.plotter import Plotter


PLOT_REFRESH_INTERVAL_MS = 33
PLOT_BACKGROUND = QColor("#1f2328")
PLOT_AXIS = QColor("#5c6370")
PLOT_GRID = QColor(92, 99, 112, 56)
PLOT_TEXT = QColor("#dce3ea")
AUTO_SCROLL_TOOLTIP = "Keep the plot view following the newest incoming data."
SHOW_ALL_TOOLTIP = "Zoom the plot out to show all captured data."


@dataclass(slots=True)
class _CurveData:
    color: QColor
    xData: list[float] = field(default_factory=list)
    yData: list[float] = field(default_factory=list)
    path: QPainterPath = field(default_factory=QPainterPath)

    def set_data(self, x_values: list[float], y_values: list[float]) -> None:
        self.xData = x_values
        self.yData = y_values
        path = QPainterPath()
        if x_values:
            path.reserve(len(x_values))
            path.moveTo(x_values[0], y_values[0])
            for x_value, y_value in zip(x_values[1:], y_values[1:]):
                path.lineTo(x_value, y_value)
        self.path = path


class _PlotCanvas(QWidget):
    """Draw stacked time-series panels and handle horizontal navigation."""

    timeRangeChanged = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._curves: dict[str, _CurveData] = {}
        self._time_range = (0.0, 10.0)
        self._drag_position: QPoint | None = None
        self._drag_range = self._time_range

    def set_curves(self, curves: dict[str, _CurveData]) -> None:
        self._curves = curves
        self.update()

    def set_time_range(self, start_time: float, end_time: float) -> None:
        self._time_range = (start_time, end_time)
        self.update()

    def plot_width(self) -> int:
        return max(1, self.width() - 80)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), PLOT_BACKGROUND)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if not self._curves:
            painter.setPen(PLOT_TEXT)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Waiting for data")
            return

        labels = list(self._curves)
        panel_height = self.height() / len(labels)
        for row, label in enumerate(labels):
            panel = QRectF(0, row * panel_height, self.width(), panel_height)
            self._draw_panel(painter, panel, label, self._curves[label])

    def _draw_panel(self, painter: QPainter, panel: QRectF, label: str, curve: _CurveData) -> None:
        plot = panel.adjusted(68, 22, -12, -30)
        if plot.width() <= 1 or plot.height() <= 1:
            return
        start_time, end_time = self._time_range
        if end_time <= start_time:
            end_time = start_time + 1.0
        minimum, maximum = _value_range(curve.yData)

        painter.setPen(PLOT_TEXT)
        painter.drawText(QRectF(plot.left(), panel.top(), plot.width(), 20),
                         Qt.AlignmentFlag.AlignCenter, label)
        axis_pen = QPen(PLOT_AXIS)
        axis_pen.setCosmetic(True)
        grid_pen = QPen(PLOT_GRID)
        grid_pen.setCosmetic(True)
        for tick in range(5):
            fraction = tick / 4
            x = plot.left() + fraction * plot.width()
            y = plot.bottom() - fraction * plot.height()
            painter.setPen(grid_pen)
            painter.drawLine(x, plot.top(), x, plot.bottom())
            painter.drawLine(plot.left(), y, plot.right(), y)
            painter.setPen(PLOT_TEXT)
            tick_box = QRectF(x - 35, plot.bottom() + 3, 70, 17)
            alignment = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
            if tick == 0:
                tick_box.moveLeft(x)
                alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            elif tick == 4:
                tick_box.moveRight(x)
                alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            painter.drawText(tick_box, alignment,
                             _format_axis_value(start_time + fraction * (end_time - start_time)))
            painter.drawText(QRectF(0, y - 9, plot.left() - 5, 18),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             _format_axis_value(minimum + fraction * (maximum - minimum)))
        painter.setPen(axis_pen)
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.topLeft(), plot.bottomLeft())
        painter.setPen(PLOT_TEXT)
        painter.drawText(QRectF(plot.left(), plot.bottom() + 18, plot.width(), 12),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "Time (s)")

        if curve.path.isEmpty():
            return
        x_scale = plot.width() / (end_time - start_time)
        y_scale = plot.height() / (maximum - minimum)
        transform = QTransform(x_scale, 0, 0, -y_scale,
                               plot.left() - start_time * x_scale,
                               plot.bottom() + minimum * y_scale)
        curve_pen = QPen(curve.color)
        curve_pen.setWidth(1)
        curve_pen.setCosmetic(True)
        painter.save()
        painter.setTransform(transform)
        painter.setClipRect(QRectF(start_time, minimum, end_time - start_time, maximum - minimum))
        painter.setPen(curve_pen)
        painter.drawPath(curve.path)
        painter.restore()

    def wheelEvent(self, event: QWheelEvent) -> None:
        start_time, end_time = self._time_range
        span = end_time - start_time
        if span <= 0:
            return
        position = min(1.0, max(0.0, (event.position().x() - 68) / self.plot_width()))
        anchor = start_time + position * span
        new_span = max(1e-9, span * (0.8 if event.angleDelta().y() > 0 else 1.25))
        new_start = anchor - position * new_span
        self.timeRangeChanged.emit(new_start, new_start + new_span)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.position().toPoint()
            self._drag_range = self._time_range
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_position is None:
            return
        start_time, end_time = self._drag_range
        delta = -(event.position().x() - self._drag_position.x()) * (end_time - start_time) / self.plot_width()
        self.timeRangeChanged.emit(start_time + delta, end_time + delta)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = None
            self.unsetCursor()
            event.accept()


class PlotWidget(QWidget):
    def __init__(self, parent=None, time_window: float = 10.0):
        super().__init__(parent)
        self.setObjectName("LivePlot")
        self.setMinimumSize(320, 220)
        self._time_window = time_window
        self._last_time_range = (0.0, time_window)
        self._series: dict[str, Plotter] = {}
        self._curves: dict[str, _CurveData] = {}
        self._visible_labels: set[str] = set()
        self._start_time: float | None = None
        self._has_pending_refresh = False

        self.graph = _PlotCanvas()
        self.graph.timeRangeChanged.connect(self.on_time_range_changed)
        self.visible_points_label = QLabel("Points: 0")
        self.visible_points_label.setToolTip("Maximum number of data points currently visible in any shown series.")
        self.downsample_ratio_label = QLabel("Downsample: 1:1")
        self.downsample_ratio_label.setToolTip("Raw visible points compared to points drawn. 1:1 means every visible point is drawn.")
        renderer_label = QLabel("QPainter")
        renderer_label.setToolTip("The graph is rendered directly by Qt's QPainter.")
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
        for widget in (self.visible_points_label, self.downsample_ratio_label, renderer_label,
                       self.series_button, self.show_all_button, self.auto_scroll_button):
            toolbar.addWidget(widget)
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
        self._curves.clear()
        self._visible_labels.clear()
        self._start_time = None
        self._has_pending_refresh = False
        self.series_menu.clear()
        self.series_button.setEnabled(False)
        self.graph.set_curves({})
        self.visible_points_label.setText("Points: 0")
        self.downsample_ratio_label.setText("Downsample: 1:1")
        self.on_toggle_auto_scroll(True)

    def replace_series(self, series: dict[str, Plotter], start_time: float | None) -> None:
        self.clear_values()
        self._series = series
        self._start_time = start_time
        self._visible_labels = set(series)
        self.auto_scroll_button.setChecked(False)
        self.show_all_button.setChecked(True)
        for label in series:
            self._add_series_menu_item(label)
        self._rebuild_plots()
        self.show_all_data()
        self._has_pending_refresh = False

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
        self._set_time_range(max(0.0, latest_time - self._time_window), max(self._time_window, latest_time))

    def show_all_data(self) -> None:
        self._set_time_range(0.0, max(self._time_window, self._latest_sample_time()))

    def _set_time_range(self, start_time: float, end_time: float) -> None:
        self._last_time_range = (start_time, end_time)
        self.graph.set_time_range(start_time, end_time)
        self._update_visible_curve_data(start_time, end_time)

    @Slot(float, float)
    def on_time_range_changed(self, start_time: float, end_time: float) -> None:
        self.auto_scroll_button.setChecked(False)
        self.show_all_button.setChecked(False)
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
        if isinstance(action, QAction) and (label := str(action.data() or "")):
            self._set_series_visibility(label, visible)

    def _set_series_visibility(self, label: str, visible: bool) -> None:
        self._visible_labels.add(label) if visible else self._visible_labels.discard(label)
        self._rebuild_plots()
        self._has_pending_refresh = True

    def _rebuild_plots(self) -> None:
        self._curves = {
            label: _CurveData(QColor(_color_for_index(row)))
            for row, label in enumerate(label for label in self._series if label in self._visible_labels)
        }
        self.graph.set_curves(self._curves)
        self.graph.set_time_range(*self._last_time_range)

    def _latest_sample_time(self) -> float:
        latest = [value for series in self._series.values() if (value := series.latest_timestamp()) is not None]
        return max(latest, default=0.0)

    def _time_range(self) -> tuple[float, float]:
        return self._last_time_range

    def _update_visible_curve_data(self, start_time: float | None = None, end_time: float | None = None) -> None:
        if start_time is None or end_time is None:
            start_time, end_time = self._time_range()
        visible_counts = []
        downsample_ratios = []
        for label, curve in self._curves.items():
            visible_samples, x_values, y_values = self._series[label].read_visible_samples(
                start_time, end_time, self._bucket_count_for_series(label)
            )
            x_values, y_values = _prepare_plot_arrays(x_values, y_values)
            visible_counts.append(visible_samples)
            curve.set_data(x_values, y_values)
            downsample_ratios.append(_downsample_ratio(visible_samples, len(x_values)))
        self.visible_points_label.setText(f"Points: {max(visible_counts, default=0):,}")
        self.downsample_ratio_label.setText(
            f"Downsample: {_format_downsample_ratio(max(downsample_ratios, default=1.0))}"
        )
        self.graph.update()

    def _bucket_count_for_series(self, _label: str) -> int:
        return max(1, self.graph.plot_width() // 4)

    def closeEvent(self, event) -> None:
        for series in self._series.values():
            series.close()
        super().closeEvent(event)


def _value_range(values: list[float]) -> tuple[float, float]:
    if not values:
        return -1.0, 1.0
    minimum, maximum = min(values), max(values)
    padding = max(0.5, abs(minimum) * 0.05) if minimum == maximum else (maximum - minimum) * 0.05
    return minimum - padding, maximum + padding


def _format_axis_value(value: float) -> str:
    if abs(value) < 1e-9:
        return "0"
    absolute = abs(value)
    return f"{value:.2e}" if absolute >= 100_000 or (absolute and absolute < 0.001) else f"{value:.4g}"


def _color_for_index(index: int) -> str:
    colors = ["#7cd1a8", "#89b4fa", "#f9c74f", "#f7768e", "#cba6f7", "#4dd0e1"]
    return colors[index % len(colors)]


def _prepare_plot_arrays(x_values: list[float], y_values: list[float]) -> tuple[list[float], list[float]]:
    points = [(x, y) for x, y in zip(x_values, y_values) if math.isfinite(x) and math.isfinite(y)]
    if not points:
        return [], []
    finite_x, finite_y = zip(*points)
    return list(finite_x), list(finite_y)


def _downsample_ratio(raw_point_count: int, plotted_point_count: int) -> float:
    return max(1.0, raw_point_count / plotted_point_count) if raw_point_count > 0 and plotted_point_count > 0 else 1.0


def _format_downsample_ratio(value: float) -> str:
    if value <= 1:
        return "1:1"
    return f"{value:.1f}:1" if value < 10 else f"{value:,.0f}:1"
