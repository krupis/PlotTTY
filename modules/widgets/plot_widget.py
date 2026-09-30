"""Live plot widget rendered directly with QPainter."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import math

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QPen, QTransform, QWheelEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QScrollArea, QFrame, QSizePolicy, QVBoxLayout, QWidget

from ..core.extraction import CapturedValue
from ..core.plotter import Plotter


PLOT_REFRESH_INTERVAL_MS = 33
PLOT_BACKGROUND = QColor("#1f2328")
PLOT_GRID = QColor(92, 99, 112, 56)
PLOT_TEXT = QColor("#dce3ea")
PLOT_LEFT_MARGIN = 68
PLOT_RIGHT_MARGIN = 12
PLOT_TOP_MARGIN = 36
PLOT_BOTTOM_MARGIN = 16
AUTO_SCROLL_TOOLTIP = "Keep the plot view following the newest incoming data."
FIT_CAPTURE_TOOLTIP = "Zoom the plot out to show all captured data."


@dataclass(slots=True)
class _CurveData:
    color: QColor
    latest: str = ""
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
        self.setToolTip(
            "Headers show the latest captured sample, including when viewing older history. "
            "Wheel or drag the plot to zoom or pan time. "
            "Wheel or drag a Y axis to adjust its range; double-click it to restore automatic range."
        )
        self.empty_message = "Waiting for series"
        self._curves: dict[str, _CurveData] = {}
        self._y_ranges: dict[str, tuple[float, float]] = {}
        self._time_range = (0.0, 10.0)
        self._drag_position: QPoint | None = None
        self._drag_range = self._time_range
        self._drag_label: str | None = None
        self._drag_y_range = (-1.0, 1.0)

    def set_curves(self, curves: dict[str, _CurveData]) -> None:
        self._curves = curves
        self.setMinimumHeight(max(150, len(curves) * 150))
        self.update()

    def set_time_range(self, start_time: float, end_time: float) -> None:
        self._time_range = _nonnegative_time_range(start_time, end_time)
        self.update()

    @property
    def time_range(self) -> tuple[float, float]:
        return self._time_range

    def clear_y_ranges(self) -> None:
        self._y_ranges.clear()

    def plot_width(self) -> int:
        return max(1, self.width() - PLOT_LEFT_MARGIN - PLOT_RIGHT_MARGIN)

    def panel_geometry(self, row):
        height = self.height() / max(1, len(self._curves))
        panel = QRectF(0, row * height, self.width(), height)
        return panel, panel.adjusted(PLOT_LEFT_MARGIN, PLOT_TOP_MARGIN,
                                      -PLOT_RIGHT_MARGIN, -PLOT_BOTTOM_MARGIN)

    def _panel_at(self, position) -> tuple[str, QRectF, QRectF] | None:
        if not self._curves or not 0 <= position.y() < self.height():
            return None
        labels = list(self._curves)
        row = min(len(labels) - 1, int(position.y() / (self.height() / len(labels))))
        return labels[row], *self.panel_geometry(row)

    def _y_range(self, label: str) -> tuple[float, float]:
        return self._y_ranges.get(label, _value_range(self._curves[label].yData))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), PLOT_BACKGROUND)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if not self._curves:
            painter.setPen(PLOT_TEXT)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.empty_message)
            return

        for row, (label, curve) in enumerate(self._curves.items()):
            panel, plot = self.panel_geometry(row)
            if panel.intersects(QRectF(_event.rect())):
                self._draw_panel(painter, panel, plot, label, curve)

    def _draw_panel(self, painter: QPainter, panel: QRectF, plot: QRectF, label: str, curve: _CurveData) -> None:
        if plot.width() <= 1 or plot.height() <= 1:
            return
        start_time, end_time = self._time_range
        if end_time <= start_time:
            end_time = start_time + 1.0
        minimum, maximum = self._y_range(label)

        painter.setPen(PLOT_TEXT)
        header = QRectF(12, panel.top() + 4, self.width() - 24, 24)
        value_width = min(header.width() * .55, painter.fontMetrics().horizontalAdvance(curve.latest) + 16)
        name_rect = header.adjusted(0, 0, -value_width, 0)
        name = painter.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(name_rect.width()))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
        painter.setPen(curve.color)
        value_rect = QRectF(header.right() - value_width, header.top(), value_width, header.height())
        painter.drawText(value_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(curve.latest, Qt.TextElideMode.ElideRight, int(value_width)))
        grid_pen = QPen(PLOT_GRID)
        grid_pen.setCosmetic(True)
        for fraction in _time_tick_fractions():
            x = plot.left() + fraction * plot.width()
            painter.setPen(grid_pen)
            painter.drawLine(x, plot.top(), x, plot.bottom())
        tick_count = 5 if plot.height() > 260 else 3
        for tick in range(tick_count):
            fraction = tick / (tick_count - 1)
            y = plot.bottom() - fraction * plot.height()
            painter.setPen(grid_pen)
            painter.drawLine(plot.left(), y, plot.right(), y)
            painter.setPen(QColor("#929da8"))
            painter.drawText(QRectF(0, y - 9, plot.left() - 8, 18),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             _format_axis_value(minimum + fraction * (maximum - minimum)))
        painter.setPen(grid_pen)
        painter.drawLine(panel.bottomLeft(), panel.bottomRight())
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
        selected = self._panel_at(event.position())
        if selected is not None and (
            event.position().x() < selected[2].left()
            or event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            label, _panel, plot = selected
            minimum, maximum = self._y_range(label)
            span = maximum - minimum
            fraction = min(1.0, max(0.0, (plot.bottom() - event.position().y()) / plot.height()))
            anchor = minimum + fraction * span
            new_span = max(1e-12, span * (0.8 if event.angleDelta().y() > 0 else 1.25))
            self._y_ranges[label] = (
                anchor - fraction * new_span,
                anchor + (1.0 - fraction) * new_span,
            )
            self.update()
            event.accept()
            return

        self.zoom_time(event.position().x(), event.angleDelta().y())
        event.accept()

    def zoom_time(self, x: float, delta: int) -> None:
        start, end = self.time_range
        fraction = min(1.0, max(0.0, (x - PLOT_LEFT_MARGIN) / self.plot_width()))
        span = max(1e-9, (end - start) * (0.8 if delta > 0 else 1.25))
        left = start + fraction * (end - start) - fraction * span
        self.timeRangeChanged.emit(*_nonnegative_time_range(left, left + span))

    def begin_drag(self, position, adjust_y=False) -> None:
        self._drag_position = position.toPoint()
        selected = self._panel_at(position) if adjust_y else None
        self._drag_label = selected[0] if selected and position.x() < selected[2].left() else None
        if self._drag_label is not None:
            self._drag_y_range = self._y_range(self._drag_label)
        else:
            self._drag_range = self._time_range

    def drag_to(self, position) -> None:
        if self._drag_position is None:
            return
        if self._drag_label is not None:
            selected = self._panel_at(self._drag_position)
            if selected is None:
                return
            minimum, maximum = self._drag_y_range
            delta = (position.y() - self._drag_position.y()) * (maximum - minimum) / max(1., selected[2].height())
            self._y_ranges[self._drag_label] = (minimum + delta, maximum + delta)
            self.update()
        else:
            start, end = self._drag_range
            delta = -(position.x() - self._drag_position.x()) * (end - start) / self.plot_width()
            self.timeRangeChanged.emit(*_nonnegative_time_range(start + delta, end + delta))

    def end_drag(self) -> None:
        self._drag_position = None
        self._drag_label = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_drag(event.position(), adjust_y=True)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.drag_to(event.position())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.end_drag()
            self.unsetCursor()
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        selected = self._panel_at(event.position())
        if (event.button() == Qt.MouseButton.LeftButton and selected is not None
                and event.position().x() < selected[2].left()):
            self._y_ranges.pop(selected[0], None)
            self.update()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


def _time_tick_fractions():
    return (0.0, .25, .5, .75, 1.0)


class _TimeAxis(QWidget):
    """Fixed shared footer; its width follows the scrolling canvas viewport."""
    def __init__(self, graph, parent=None):
        super().__init__(parent)
        self.graph = graph
        self.setFixedHeight(34)
        self.setToolTip("Elapsed time (seconds). Wheel or drag to navigate time.")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), PLOT_BACKGROUND)
        painter.setPen(QColor("#929da8"))
        start, end = self.graph.time_range
        for fraction in _time_tick_fractions():
            x = PLOT_LEFT_MARGIN + fraction * self.graph.plot_width()
            box = QRectF(x - 40, 5, 80, 24)
            alignment = Qt.AlignmentFlag.AlignHCenter
            if fraction == 0:
                box.moveLeft(x)
                alignment = Qt.AlignmentFlag.AlignLeft
            elif fraction == 1:
                box.moveRight(x)
                alignment = Qt.AlignmentFlag.AlignRight
            painter.drawText(box, alignment, _format_time_value(start + fraction * (end - start), end - start) + " s")

    def wheelEvent(self, event):
        self.graph.zoom_time(event.position().x(), event.angleDelta().y())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.graph.begin_drag(event.position())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        self.graph.drag_to(event.position())
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.graph.end_drag()
            self.unsetCursor()
            event.accept()


class _CaptureTitle(QLabel):
    """Keep full capture names available while fitting the shared toolbar."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, self.contentsRect().width())
        painter.drawText(self.contentsRect(), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)


class PlotWidget(QWidget):
    seriesChanged = Signal()

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
        self.time_axis_label = _TimeAxis(self.graph)
        self.scroll_area = QScrollArea()
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.graph)
        self.capture_title = _CaptureTitle("")
        self.capture_title.hide()
        self.capture_title.setObjectName("CaptureTitle")
        self.capture_title.setTextFormat(Qt.TextFormat.PlainText)
        self.capture_title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.capture_title.setMaximumWidth(240)
        self.auto_scroll_button = QPushButton("Auto scroll")
        self.auto_scroll_button.setObjectName("PlotModeButton")
        self.auto_scroll_button.setCheckable(True)
        self.auto_scroll_button.setChecked(True)
        self.auto_scroll_button.setToolTip(AUTO_SCROLL_TOOLTIP)
        self.auto_scroll_button.clicked.connect(self.on_toggle_auto_scroll)
        self.fit_capture_button = QPushButton("Fit capture")
        self.fit_capture_button.setObjectName("PlotModeButton")
        self.fit_capture_button.setCheckable(True)
        self.fit_capture_button.setToolTip(FIT_CAPTURE_TOOLTIP)
        self.fit_capture_button.clicked.connect(self.on_toggle_fit_capture)

        toolbar = self.controls_layout = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(self.capture_title)
        for widget in (self.fit_capture_button, self.auto_scroll_button):
            toolbar.addWidget(widget)
        self.visible_points_label.hide()
        self.downsample_ratio_label.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        self.series_selector = QWidget(self)
        self.series_selector.setObjectName("SeriesSelector")
        self.series_selector_layout = QHBoxLayout(self.series_selector)
        self.series_selector_layout.setContentsMargins(0, 0, 0, 0)
        self.series_selector_layout.setSpacing(8)
        self.series_selector.hide()
        layout.addWidget(self.series_selector)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.time_axis_label)
        self._timer = QTimer(self)
        self._timer.setInterval(PLOT_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.on_refresh_pending_data)
        self._timer.start()

    def attach_series_selector(self, heading: QLabel, series_list: QListWidget) -> None:
        """Keep series visibility controls immediately above the plot panels."""
        heading.setParent(self.series_selector)
        series_list.setParent(self.series_selector)
        series_list.setFlow(QListWidget.Flow.LeftToRight)
        series_list.setWrapping(False)
        series_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        series_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        series_list.setFixedHeight(42)
        self.series_selector_layout.addWidget(heading)
        self.series_selector_layout.addWidget(series_list, 1)
        self.series_selector.show()

    @Slot(list)
    def append_values(self, values: Iterable[CapturedValue]) -> None:
        added_series = False
        for captured in values:
            if self._start_time is None:
                self._start_time = captured.timestamp
            if captured.label not in self._series:
                self._series[captured.label] = Plotter()
                self._visible_labels.add(captured.label)
                added_series = True
            series = self._series[captured.label]
            if captured.unit and captured.unit != series.unit:
                added_series = True
            series.add_sample(captured.timestamp - self._start_time, captured.value, captured.unit)
            self._has_pending_refresh = True
        if added_series:
            self._rebuild_plots()
            self.seriesChanged.emit()

    def clear_values(self) -> None:
        for series in self._series.values():
            series.close()
        self._series.clear()
        self._curves.clear()
        self._visible_labels.clear()
        self._start_time = None
        self._has_pending_refresh = False
        self.graph.clear_y_ranges()
        self.graph.empty_message = "Waiting for series"
        self.capture_title.clear()
        self.capture_title.hide()
        self.capture_title.setToolTip("")
        self.graph.set_curves({})
        self.visible_points_label.setText("Points: 0")
        self.downsample_ratio_label.setText("Downsample: 1:1")
        self.on_toggle_auto_scroll(True)
        self.seriesChanged.emit()

    def replace_series(self, series: dict[str, Plotter], start_time: float | None) -> None:
        self.clear_values()
        self._series = series
        self._start_time = start_time
        self._visible_labels = set(series)
        self.auto_scroll_button.setChecked(False)
        self.fit_capture_button.setChecked(True)
        self._rebuild_plots()
        self.fit_capture()
        self.seriesChanged.emit()
        self._has_pending_refresh = False

    @Slot()
    def on_refresh_pending_data(self) -> None:
        if not self._has_pending_refresh:
            return
        self._has_pending_refresh = False
        if self.auto_scroll_button.isChecked():
            self.show_recent_data()
        elif self.fit_capture_button.isChecked():
            self.fit_capture()
        else:
            self._update_visible_curve_data()

    @Slot(bool)
    def on_toggle_auto_scroll(self, enabled: bool) -> None:
        self.auto_scroll_button.setChecked(enabled)
        if enabled:
            self.fit_capture_button.setChecked(False)
            self.show_recent_data()

    @Slot(bool)
    def on_toggle_fit_capture(self, enabled: bool) -> None:
        self.fit_capture_button.setChecked(enabled)
        if enabled:
            self.auto_scroll_button.setChecked(False)
            self.fit_capture()

    def show_recent_data(self) -> None:
        latest_time = self._latest_sample_time()
        self._set_time_range(max(0.0, latest_time - self._time_window), max(self._time_window, latest_time))

    def fit_capture(self) -> None:
        self._set_time_range(0.0, max(self._time_window, self._latest_sample_time()))

    def _set_time_range(self, start_time: float, end_time: float) -> None:
        start_time, end_time = _nonnegative_time_range(start_time, end_time)
        self._last_time_range = (start_time, end_time)
        self.graph.set_time_range(start_time, end_time)
        self.time_axis_label.update()
        self._update_visible_curve_data(start_time, end_time)

    @Slot(float, float)
    def on_time_range_changed(self, start_time: float, end_time: float) -> None:
        self.auto_scroll_button.setChecked(False)
        self.fit_capture_button.setChecked(False)
        self._set_time_range(start_time, end_time)

    def series_info(self):
        return [{"label": label, "unit": series.unit, "color": QColor(_color_for_index(row)),
                 "visible": label in self._visible_labels}
                for row, (label, series) in enumerate(self._series.items())]

    def set_series_visible(self, label: str, visible: bool) -> None:
        if label not in self._series or (label in self._visible_labels) == visible:
            return
        self._visible_labels.add(label) if visible else self._visible_labels.discard(label)
        self._rebuild_plots()
        self._has_pending_refresh = True
        self.seriesChanged.emit()

    def update_series_labels(self, labels: dict[str, str]) -> None:
        """Rename plotted rule-backed series while retaining their captured history."""
        labels = {old: new for old, new in labels.items() if old != new and old in self._series}
        if not labels:
            return
        renamed = {}
        visible = set()
        for label, series in self._series.items():
            new_label = labels.get(label, label)
            # Two rules with the same new label intentionally share subsequent samples.
            # Keep the existing history rather than silently discarding it on a collision.
            if new_label not in renamed:
                renamed[new_label] = series
            if label in self._visible_labels:
                visible.add(new_label)
        self._series = renamed
        self._visible_labels = visible
        self.graph._y_ranges = {
            labels.get(label, label): value for label, value in self.graph._y_ranges.items()
        }
        self._rebuild_plots()
        self._has_pending_refresh = True
        self.seriesChanged.emit()

    def _rebuild_plots(self) -> None:
        self._curves = {
            label: _CurveData(QColor(_color_for_index(row)))
            for row, label in enumerate(self._series) if label in self._visible_labels
        }
        self.graph.empty_message = "No series selected" if self._series else "Waiting for series"
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
            series = self._series[label]
            latest = series.latest_value()
            curve.latest = (_format_axis_value(latest) + (" " + series.unit if series.unit else "")) if latest is not None else "—"
            visible_samples, x_values, y_values = self._series[label].read_visible_samples(
                start_time, end_time, self._bucket_count_for_series(label)
            )
            x_values, y_values = _prepare_plot_arrays(x_values, y_values)
            curve.set_data(x_values, y_values)
            visible_counts.append(visible_samples)
            downsample_ratios.append(_downsample_ratio(visible_samples, len(x_values)))
        self.visible_points_label.setText(f"Points: {max(visible_counts, default=0):,}")
        self.downsample_ratio_label.setText(
            f"Downsample: {_format_downsample_ratio(max(downsample_ratios, default=1.0))}"
        )
        self.graph.update()

    def _bucket_count_for_series(self, _label: str) -> int:
        return max(1, self.graph.plot_width() // 4)

    def resizeEvent(self, event):
        self._has_pending_refresh = True
        self.time_axis_label.update()
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        for series in self._series.values():
            series.close()
        self._series.clear()
        super().closeEvent(event)


def _value_range(values: list[float]) -> tuple[float, float]:
    if not values:
        return -1.0, 1.0
    minimum, maximum = min(values), max(values)
    padding = max(0.5, abs(minimum) * 0.05) if minimum == maximum else (maximum - minimum) * 0.05
    return minimum - padding, maximum + padding


def _nonnegative_time_range(start_time: float, end_time: float) -> tuple[float, float]:
    span = max(1e-9, end_time - start_time)
    if start_time < 0:
        return 0.0, span
    return start_time, start_time + span


def _format_axis_value(value: float) -> str:
    if abs(value) < 1e-9:
        return "0"
    absolute = abs(value)
    return f"{value:.2e}" if absolute >= 100_000 or (absolute and absolute < 0.001) else f"{value:.4g}"


def _format_time_value(value: float, visible_span: float) -> str:
    """Format elapsed seconds without switching to scientific notation."""
    tick_step = abs(visible_span) / 4
    if tick_step >= 10:
        decimal_places = 0
    elif tick_step >= 1:
        decimal_places = 1
    elif tick_step >= 0.1:
        decimal_places = 2
    elif tick_step >= 0.01:
        decimal_places = 3
    else:
        decimal_places = 6
    text = f"{value:,.{decimal_places}f}"
    if decimal_places:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "-0.0") else text


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
