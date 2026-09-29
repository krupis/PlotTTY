"""Measure the current app against a serial device. No commands are transmitted."""
import argparse
from collections import defaultdict
from functools import wraps
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow, apply_application_style
from modules.core.extraction import ExtractionRule
from modules.core.serial_transport import SerialSettings
from modules.controllers.serial_session import SerialSession
from modules.widgets.console_widget import ConsoleWidget
from modules.widgets.plot_widget import PlotWidget
from plot_benchmark import stats
from ui_latency import EventLoopLatencyMonitor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--duration", type=float, default=25)
    parser.add_argument("--warmup", type=float, default=10)
    parser.add_argument("--no-logging", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.duration <= 0 or args.warmup < 0:
        parser.error("duration must be positive and warmup nonnegative")
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_application_style(app)
    timings = defaultdict(list)
    counts = {"bytes": 0, "values": 0}
    errors = []
    active = False

    def instrument(cls, method):
        original = getattr(cls, method)
        @wraps(original)
        def timed(self, *a, **kw):
            if not active:
                return original(self, *a, **kw)
            tick = perf_counter()
            try:
                return original(self, *a, **kw)
            finally:
                timings[method].append((perf_counter() - tick) * 1000)
        setattr(cls, method, timed)

    for cls, method in ((SerialSession, "on_receive"), (ConsoleWidget, "flush"),
                        (PlotWidget, "append_values"), (PlotWidget, "_update_visible_curve_data")):
        instrument(cls, method)
    # Avoid modal errors during unattended device measurements.
    MainWindow.on_serial_error = lambda self, message: errors.append(message)
    window = MainWindow()
    window._preferences = QSettings(str(args.output.resolve() / "layout.ini"), QSettings.Format.IniFormat)
    window.resize(1280, 720)
    window.apply_rules([ExtractionRule(f"Value {i}", "delimiter_column", extra_setting=str(i)) for i in range(6)])
    window.apply_settings(SerialSettings(port=args.port, log_to_file=not args.no_logging))
    window.session._serial_log.log_dir = args.output
    window.session._plot_log.log_dir = args.output
    window.show()
    app.processEvents()
    window.ui.actionConsole.setChecked(True)
    window.plot.on_toggle_fit_capture(True)
    monitor = EventLoopLatencyMonitor(window)
    monitor.start()
    try:
        window.session.connect_serial()
    except Exception as exc:
        window.close()
        raise SystemExit(str(exc))

    def received(data, _timestamp):
        if active:
            counts["bytes"] += len(data)
    def captured(values):
        if active:
            counts["values"] += len(values)
    window.session._connection.bytesReceived.connect(received)
    window.session.valuesCaptured.connect(captured)
    started = 0.

    def begin():
        nonlocal active, started
        monitor._latencies_ms.clear()
        started = perf_counter()
        active = True
        QTimer.singleShot(round(args.duration * 1000), finish)

    def finish():
        nonlocal active
        active = False
        elapsed = perf_counter() - started
        window.session.disconnect_serial()
        window.grab().save(str(args.output / "window.png"))
        result = {"elapsed_seconds": elapsed, "counts": counts, "errors": errors,
                  "receive_bytes_per_second": counts["bytes"] / elapsed,
                  "latency": monitor.summary(), "stages": {name: stats(values) for name, values in timings.items()},
                  "samples_per_series": {label: store.sample_count() for label, store in window.plot._series.items()},
                  "qt_platform": app.platformName()}
        (args.output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        window.close()
        app.quit()

    QTimer.singleShot(round(args.warmup * 1000), begin)
    app.exec()
    if errors:
        raise SystemExit("Serial errors occurred; see result.json")


if __name__ == "__main__":
    main()
