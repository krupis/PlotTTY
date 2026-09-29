# PlotTTY performance checks

These tools use the application's PySide6 dependency and the Python standard
library. No NumPy, plotting libraries, OpenGL packages, or extra installation is
needed. Run from the repository root with the application Python environment.

## Plot and storage benchmark

```sh
python benchmarks/plot_benchmark.py --output /tmp/plottty-benchmark
```

Quick smoke check:

```sh
python benchmarks/plot_benchmark.py --frames 5 --repeats 1 --raw-samples 10000 --output /tmp/plottty-smoke
```

The benchmark uses five deterministic series in a 1000×900 logical-pixel window.
It measures fixed-range refresh and changing-range navigation with the production
QPainter canvas, Plotter storage, and bucket reduction. Each repeat includes ten
warmups followed by the requested measured frames. Default settings are 40 frames,
three repeats, and one million raw samples per series.

`current-widget.json` contains raw timing samples, median/p95/maximum service times,
point counts, storage-read timings, and environment information. A PNG accompanies
it. Keep data, dimensions, scaling, and machine load identical when comparing runs.
These are synchronous update/render timings, not displayed FPS or input latency.

## Live serial diagnostics

```sh
python benchmarks/live_serial_diagnostics.py --port COM15 --duration 25 --warmup 10 --output /tmp/plottty-live
```

This opens the real app at 115200 baud with six comma-delimited extraction rules
(fields 0–5), Fit capture, and the console visible. It sends no commands. It records
receive counts, stage timings, timer lateness, sample counts, errors, and a screenshot.
Recordings and isolated layout preferences go into the output directory; use
`--no-logging` to measure without recording. Choose a fresh output directory for
each run. Stage times can overlap and should not be added as exclusive CPU costs.

The latency monitor lives only in this developer tool. The app's View → Diagnostics
shows point counts and downsampling, without a background latency-sampling timer.

Use a real desktop session for display performance work. For automated smoke checks,
`QT_QPA_PLATFORM=offscreen` is useful, but its timings are not equivalent to a native
window. Physical serial hardware is required for meaningful live measurements.

## Historical experiments

[Renderer comparison](RESULTS.md) and [live-latency investigation](LIVE_LATENCY.md)
retain earlier measurements. Their alternative-renderer implementations, conversion
script, and chart generator have been retired; the historical code is available in
Git history. Those results describe the implementation measured at that time.
