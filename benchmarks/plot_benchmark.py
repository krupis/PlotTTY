"""Measure the current QPainter widget and sample storage; no extra dependencies."""
import argparse
import json
import math
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter, perf_counter_ns

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import qVersion
from PySide6.QtWidgets import QApplication
from modules.core.plotter import Plotter
from modules.widgets.plot_widget import PlotWidget, _prepare_plot_arrays


def stats(values):
    ordered = sorted(values)
    def percentile(percent):
        index = (len(ordered) - 1) * percent
        lower = int(index)
        return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (index - lower)
    return {"median_ms": statistics.median(ordered), "p95_ms": percentile(.95), "max_ms": ordered[-1]}


def run(args, app):
    widget = PlotWidget()
    widget._timer.stop()
    widget.resize(1000, 900)
    started = perf_counter()
    series = {}
    for j in range(5):
        store = series[f"Value {j + 1}"] = Plotter()
        for i in range(args.raw_samples):
            store.add_sample(i * .001, math.sin(i * .07 + j))
    build_seconds = perf_counter() - started
    widget.replace_series(series, 0.)
    for label in series:
        widget.set_series_style(label, args.style)
    widget.show()
    app.processEvents()
    latest = (args.raw_samples - 1) * .001
    rows = []
    for mode in ("refresh", "pan_zoom"):
        timings = []
        for _ in range(args.repeats):
            for k in range(args.frames + 10):
                span = latest if mode == "refresh" else latest * (.55 + .35 * math.sin(k * .12) ** 2)
                start = 0 if mode == "refresh" else (latest - span) * .5
                tick = perf_counter_ns()
                widget._set_time_range(start, start + span)
                widget.graph.repaint()
                app.processEvents()
                if k >= 10:
                    timings.append((perf_counter_ns() - tick) / 1e6)
        rows.append({"mode": mode, "raw_samples_per_series": args.raw_samples,
                     "plotted_points_per_series": [len(curve.xData) for curve in widget._curves.values()],
                     **stats(timings), "samples_ms": timings})
    widget.grab().save(str(args.output / "current-widget.png"))
    timings = []
    for _ in range(args.frames * args.repeats):
        tick = perf_counter_ns()
        for label, store in series.items():
            _, x, y = store.read_visible_samples(0, latest, widget._bucket_count_for_series(label))
            _prepare_plot_arrays(x, y)
        timings.append((perf_counter_ns() - tick) / 1e6)
    result = {"backend": "current-widget", "build_seconds": build_seconds, "rows": rows,
              "style": args.style,
              "storage_read_five_series": stats(timings),
              "environment": {"python": sys.version, "platform": platform.platform(), "qt": qVersion(),
                              "qt_platform": app.platformName(), "device_pixel_ratio": widget.devicePixelRatioF(),
                              "logical_size": [widget.width(), widget.height()]}}
    widget.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=40)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--raw-samples", type=int, default=1_000_000)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--style", choices=("lines", "dots"), default="lines")
    args = parser.parse_args()
    if min(args.frames, args.repeats) < 1 or args.raw_samples < 2:
        parser.error("frames/repeats must be positive and raw-samples must be at least 2")
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    errors = []
    def report_error(kind, value, traceback):
        errors.append(value)
        sys.__excepthook__(kind, value, traceback)
    sys.excepthook = report_error
    result = run(args, app)
    if errors:
        raise RuntimeError("Qt callback failed during benchmark") from errors[0]
    (args.output / "current-widget.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    for row in result["rows"]:
        print(f"{row['mode']}: median {row['median_ms']:.2f} ms; p95 {row['p95_ms']:.2f} ms")


if __name__ == "__main__":
    main()
