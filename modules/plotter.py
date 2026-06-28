"""In-memory data storage for plotted series."""

from __future__ import annotations

from bisect import bisect_left, bisect_right


class Plotter:
    """Store ordered X/Y samples and return visible slices."""

    def __init__(self):
        self._x_values: list[float] = []
        self._y_values: list[float] = []

    def add_sample(self, timestamp: float, value: float) -> None:
        self._x_values.append(timestamp)
        self._y_values.append(value)

    def read_visible_samples(self, start_time: float, end_time: float, max_points: int) -> tuple[list[float], list[float]]:
        start_index, stop_index = self._indexes_for_range(start_time, end_time)
        x_values = self._x_values[start_index:stop_index]
        y_values = self._y_values[start_index:stop_index]

        if len(x_values) <= max_points:
            return x_values, y_values

        step = max(1, len(x_values) // max_points)
        return x_values[::step], y_values[::step]

    def count_visible_samples(self, start_time: float, end_time: float) -> int:
        start_index, stop_index = self._indexes_for_range(start_time, end_time)
        return max(0, stop_index - start_index)

    def latest_timestamp(self) -> float | None:
        if not self._x_values:
            return None
        return self._x_values[-1]

    def clear(self) -> None:
        self._x_values.clear()
        self._y_values.clear()

    def _indexes_for_range(self, start_time: float, end_time: float) -> tuple[int, int]:
        return (
            bisect_left(self._x_values, start_time),
            bisect_right(self._x_values, end_time),
        )
