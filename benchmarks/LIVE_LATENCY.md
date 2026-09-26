# COM15 live latency investigation ? 2026-09-24

The main problem was GUI-thread plotting work and refresh scheduling, rather
than serial parsing or insufficient GPU line-rendering speed. With the actual
device connected, enabling OpenGL alone did not materially improve UI timer
latency. The final changes reduce p95 timer lateness by about **57%** in the
matched OpenGL comparison, while retaining every captured sample and both logs.

## Matched longer captures

Each run uses ten seconds of warmup followed by sixty seconds of measurement.
The baseline was rerun from an isolated source snapshot after the optimized run,
without reverting the working tree. All three windows were exposed and not
minimized throughout the recorded timeline; all reported zero errors.

Times are milliseconds. Update rate is measured curve-data refreshes per second,
not monitor scanout FPS.

| Configuration | Median | p95 | p99 | Worst tick | Plot updates/s |
|---|---:|---:|---:|---:|---:|
| Original, OpenGL, 20 ms setting | 28.9 | 48.9 | 54.4 | 96.1 | 23.8 |
| Updated, OpenGL, 33 ms setting | 4.3 | 21.2 | 25.4 | 77.3 | 21.3 |
| Updated, CPU, 33 ms setting | 0.6 | 19.9 | 22.5 | 66.4 | 21.3 |

This is a responsiveness tradeoff: the requested display interval changed from
20 to 33 ms, and actual curve updates fell from about 24 to 21 per second.
Acquisition remained about **2,000 rows/second**, **12,000 values/second**, or
**100 kB/second**. No acquisition-rate reduction, data dropping, rule disabling,
or logging disabling was used for these comparisons. The OpenGL default and
runtime toggle are retained. The small difference between final CPU and GPU
results is not evidence that one is universally better.

## Device and UI setup

- COM15, 115200 baud, 8 data bits, no parity, one stop bit; UTF-8.
- Receive-only testing: the diagnostic never calls `send_command` or transmits
  application commands. It uses the normal serial connection open/close path.
- Six enabled comma-delimited Y rules: fields 0 through 5, labels Value 0..5.
  None is marked as the X counter, matching the screenshot. The saved uCurrent
  profile marks field 0 as a counter, so it was deliberately not used for this test.
- Receive timestamps on X; **See all plot** active; rules tab visible, console
  hidden but still receiving/rendering buffered text; console's 10,000-line cap on.
- Console and plot CSV logs enabled, full styled MainWindow, 1880 x 1000 window.
- Same installed Python/Qt/pyqtgraph environment as the plotting benchmark.

The metric measures how late the application's precise 16 ms UI timer fires.
The report uses all ticks in the measurement interval, following warmup. The
status bar normally reports a rolling window of at most 600 ticks, so a single
status-bar reading can differ. This is **not device-to-screen latency** or a
measurement of USB hardware transport time.

## Diagnosis and intermediate experiments

The original 25-second baseline was 48.4 ms p95 in GL mode and 47.5 ms in CPU
mode. Pausing only plot refreshes, while still extracting/storing/logging all
incoming values and updating the console, lowered p95 to **2.5 ms**. No counter
gaps were detected in those measurement intervals.

In the longer original GL run, paint handling consumed about 37.5% of elapsed
wall time and plot range/data preparation another 17.9%. All receive processing
(including parsing, logging, and storage) consumed about 15.7%; console flushing
another 8.1%. These are synchronous **wall-time shares**, not hardware CPU/GPU
utilization. Stage timings are nested; inclusive totals must not be added again
to their child totals.

The more detailed original rendering run measured about 4.0 seconds of axis
painting/layout versus 2.1 seconds of curve painting over 25 seconds. OpenGL
accelerates the latter but does not remove axes, scene updates, or event-loop
contention.

| Experiment (25 s measurement) | UI p95 (ms) |
|---|---:|
| Original OpenGL | 48.4 |
| Original CPU rendering | 47.5 |
| Plot refresh paused; capture/logging/console retained | 2.5 |
| Requested vsync off, visible window | 48.4 |
| Avoid redundant full-history disk lookup | 43.6 |
| Disk lookup optimization + 33 ms timer only | 35.3 |
| Disk lookup optimization + early scene preparation, 20 ms timer | 28.9 |
| Disk lookup optimization + early preparation + 33 ms timer | 20.5 |
| Same, with Qt precise plot timer | 20.8 |

An earlier synchronization trial recorded no paint events. It was excluded;
visibility/exposure checks were added and the visible repeat reproduced the
original latency. Precise timer mode and requested vsync changes did not improve
the validated result and were not added to production.

## Production changes

1. **Plotter range lookup:** remember the first timestamp, recognize ranges that
   cover the known capture boundaries, and skip redundant binary searches and
   disk flushes in the common full-history view. Raw reads still flush pending
   data first; interior bounds still use the existing binary search. Median
   per-series read/downsample time fell from about 0.69 to 0.39 ms in the longer
   captures. Duplicate timestamps and exact inclusive endpoints are preserved.
2. **Prepare ranges/transforms before paint:** call the existing pyqtgraph scene
   preparation method after submitting the curves. This resolves pending
   auto-range/transform work before Qt enters painting, reducing the opportunity
   for range changes during paint to request further repaints. This alone helped
   at the original refresh setting; it is not merely a lower frame-rate result.
3. **Display scheduling:** use a 33 ms refresh interval to leave more room for
   input and serial callbacks between six-panel redraws. Storage, extraction,
   and file logging continue independently for every incoming value.
4. Corrected the OpenGL tooltip: a 600-sample latency window takes longer than
   ten seconds to refill when the event loop is delayed.

No new application dependencies, thread architecture changes, renderer replacement,
parser rewrite, envelope rendering, or further bucket-level changes were needed.
The existing powers-of-two bucket levels and runtime OpenGL toggle remain.

## Data integrity and regression validation

All six CSV series exactly matched the in-memory per-series sample counts,
including warmup:

| Capture | Samples in each of six series | Counter discontinuities |
|---|---:|---:|
| Original GL repeat | 140,163 | 0 |
| Updated GL | 140,189 | 0 |
| Updated CPU | 140,285 | 0 |

All measured input lines in those runs yielded six values. The field-0 sequence
was contiguous both during measurement and when independently reading the entire
CSV afterward. This is evidence of no observed loss for these captures, not a
universal guarantee for all hardware/rates.

Four storage regression tests pass: summary reads without unnecessary disk access,
buffered raw reads, duplicate timestamps/exact boundaries/interior and empty
ranges, and an empty capture. Real Qt/OpenGL checks passed for repeated renderer
switches, manual X/Y range retention, manual Y mode, hiding/showing series,
auto-scroll, continued sample updates, clear, and empty plots. Python compilation
and Git whitespace checks pass.

Occasional **66?77 ms worst-tick delays remain** in the optimized captures.
Long receive/extraction/append calls were observed; their rare-spike cause was
not isolated. No claim is made that worst-case pauses have been eliminated.
The live measurements emphasize the screenshot's full-history view; other
navigation modes were functionally checked, not comprehensively benchmarked.

## Artifacts and rerunning

- [Diagnostic runner](live_serial_diagnostics.py).
- [Measured stage summaries and data-validation results](live_latency_measurements.json).
- Full result JSON, timeline samples, screenshots, console logs, and CSV logs:
  `logs/latency_diagnostics/<run>/` locally (ignored by Git).
- Original source snapshot: `logs/latency_diagnostics/baseline_source/` locally.
  Original Plotter came from HEAD, where it was unmodified at baseline; the
  original widget was copied before changes. Recorded file hashes identify the
  source used by the longer comparison runs.

Close/disconnect any other application using COM15. Keep the diagnostic window
visible and do not interact with it during a measurement:

```powershell
.venv\Scripts\python.exe benchmarks/live_serial_diagnostics.py --renderer gl --duration 60 --output logs/latency_diagnostics/my_gl_run
.venv\Scripts\python.exe benchmarks/live_serial_diagnostics.py --renderer raster --duration 60 --output logs/latency_diagnostics/my_cpu_run
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use a new output directory for each run. The runner connects automatically with
the six screenshot rules, disconnects afterward, and closes its window. Optional
flags isolate console output, plot refresh, logging, frame interval, detailed
axis/curve timings, and cProfile (`--profile`). Those isolation flags change the
workload and should not be described as normal-application performance.

Only `plotter.py` and `plot_widget.py` are overridden by the optional
`--source-snapshot` switch; other code and dependencies come from the working
tree. Instrumentation adds some overhead. Runs are sequential local experiments,
not randomized trials or multi-device guarantees. COM15 was released after testing.
