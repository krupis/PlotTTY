"""One cancellable background job for loading captures or exporting CSV."""

from pathlib import Path
from time import monotonic

from PySide6.QtCore import QThread, Signal

from ..core.binary_logging import CaptureCancelled, export_capture_csv, iter_binary_capture
from ..core.plotter import Plotter


class CaptureJob(QThread):
    progress = Signal(int)

    def __init__(self, path: str | Path, destination: str | Path | None = None, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.destination = Path(destination) if destination is not None else None
        self.series: dict[str, Plotter] = {}
        self.start_time: float | None = None
        self.row_count = 0
        self.error: str | None = None
        self.cancelled = False
        self._last_progress = 0.0

    def run(self) -> None:
        try:
            if self.destination is not None:
                self.row_count = export_capture_csv(
                    self.path, self.destination, self._report, self.isInterruptionRequested
                )
            else:
                self._load()
        except CaptureCancelled:
            self.cancelled = True
        except Exception as exc:
            self.error = str(exc)
        finally:
            if self.cancelled or self.error is not None:
                self.discard_series()

    def _load(self) -> None:
        # These stores belong to the worker until finished; no GUI objects here.
        for batch in iter_binary_capture(self.path):
            self._check_cancelled()
            for captured in batch:
                if self.start_time is None:
                    self.start_time = captured.timestamp
                if captured.label not in self.series:
                    self.series[captured.label] = Plotter()
                self.series[captured.label].add_sample(captured.timestamp - self.start_time, captured.value, captured.unit)
            self.row_count += len(batch)
            self._report(self.row_count)
        self._check_cancelled()

    def _check_cancelled(self) -> None:
        if self.isInterruptionRequested():
            raise CaptureCancelled()

    def _report(self, count: int) -> None:
        now = monotonic()
        if now - self._last_progress >= .1:
            self.progress.emit(count)
            self._last_progress = now

    def take_series(self) -> dict[str, Plotter]:
        """Transfer the completed stores to the GUI thread."""
        if self.isRunning():
            raise RuntimeError("Capture job is still running")
        series, self.series = self.series, {}
        return series

    def discard_series(self) -> None:
        """Release unclaimed stores after failure, cancellation, or window close."""
        for series in self.series.values():
            series.close()
        self.series.clear()
