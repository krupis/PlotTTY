"""Small event-loop latency monitor for interactive performance checks."""

from __future__ import annotations

from collections import deque
from time import perf_counter

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot


LATENCY_SAMPLE_INTERVAL_MS = 16
LATENCY_REPORT_INTERVAL_MS = 1000
LATENCY_WINDOW_SIZE = 600


class EventLoopLatencyMonitor(QObject):
    """Measure how late a precise QTimer fires while the UI is under load."""

    summaryChanged = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._latencies_ms: deque[float] = deque(maxlen=LATENCY_WINDOW_SIZE)
        self._expected_next_tick: float | None = None
        self._last_report = perf_counter()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(LATENCY_SAMPLE_INTERVAL_MS)
        self._timer.timeout.connect(self.on_tick)

    def start(self) -> None:
        now = perf_counter()
        self._expected_next_tick = now + LATENCY_SAMPLE_INTERVAL_MS / 1000.0
        self._last_report = now
        self._timer.start()

    @Slot()
    def on_tick(self) -> None:
        now = perf_counter()
        if self._expected_next_tick is not None:
            latency_ms = max(0.0, (now - self._expected_next_tick) * 1000.0)
            self._latencies_ms.append(latency_ms)

        self._expected_next_tick = now + LATENCY_SAMPLE_INTERVAL_MS / 1000.0
        if now - self._last_report >= LATENCY_REPORT_INTERVAL_MS / 1000.0:
            self._last_report = now
            self.summaryChanged.emit(self.summary())

    def summary(self) -> str:
        if not self._latencies_ms:
            return "UI p95: -- ms  p99: -- ms"

        values = sorted(self._latencies_ms)
        p95 = _percentile(values, 95)
        p99 = _percentile(values, 99)
        worst = values[-1]
        return f"UI p95: {p95:.1f} ms  p99: {p99:.1f} ms  max: {worst:.1f} ms"


def _percentile(sorted_values: list[float], percentile: int) -> float:
    index = round((len(sorted_values) - 1) * percentile / 100)
    return sorted_values[index]
