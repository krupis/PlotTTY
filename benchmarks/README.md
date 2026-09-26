# Plot rendering comparison

This is an isolated experiment; it does not change the application's plot widget
or its requirements. See [RESULTS.md](RESULTS.md) for measured results and the
replacement assessment.

Live-device diagnostics are separate: see [LIVE_LATENCY.md](LIVE_LATENCY.md) for
the COM15 investigation, before/after measurements, and rerun instructions.

## Run on Windows

From the repository root, using the existing application virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install --target benchmarks/_deps -r benchmarks/requirements.txt
.venv\Scripts\python.exe benchmarks/plot_backends.py --output benchmarks/results/full
```

The benchmark opens real windows sequentially. Leave them visible and avoid
interacting with them. A desktop session and working graphics driver are needed;
headless/offscreen numbers are not equivalent. Optional dependencies are confined
to `_deps`, which only the benchmark adds to its Python import path.

For a quick check:

```powershell
.venv\Scripts\python.exe benchmarks/plot_backends.py --frames 5 --repeats 1 --points 1000 --raw-samples 10000 --output benchmarks/results/smoke
```

Use `--backends pyqtgraph pyqtgraph-gl`, for example, to select implementations.
JSON includes individual timing samples, median, p95, maximum, package versions,
and platform information. PNG screenshots and process logs accompany the data.
Each implementation runs in its own process; failures are reported explicitly.

To print tables and regenerate the chart:

```powershell
.venv\Scripts\python.exe benchmarks/summarize.py benchmarks/results/full --chart benchmarks/comparison.svg
```

## What is measured

- Five stacked series in a 1000 x 900 logical-pixel window.
- 1,000, 10,000, and 100,000 submitted points **per series**. No backend may
  automatically downsample. Matplotlib path simplification is disabled.
- Identical deterministic signals: a sine wave plus a smaller, higher-frequency
  component. Arrays are generated before timing; backend conversions and GPU
  uploads are timed. The waveform's frequency does not grow with point count.
- `refresh`: changing all five Y arrays while the axes stay fixed.
- `pan_zoom`: changing all five arrays and programmatically changing the X range.
  This includes tick/label updates in the full plotting libraries.
- Forty timed iterations after ten warmups, repeated three times per case.
  Median and p95 pool the 120 timed iterations.
- Synchronous Qt repaint/event processing; OpenGL cases additionally call
  `glFinish` so GPU submission alone is not mistaken for completed rendering.
  Vsync is requested off. These are update-and-render service times, **not**
  measured display FPS, input latency, or an assertion about scanout timing.
- Separate `current-widget` and `current-widget-gl` cases use the actual
  `PlotWidget`, `Plotter`, and `Buckets`, with 1,000,000 raw samples per series.
  They time 40 refreshes and 40 range changes after ten warmups. Their timer is
  stopped and stored history is fixed; ingestion, serial parsing, and logging
  are not part of those timings. Storage reads/conversion are also timed alone.

The normal application asks for `view_width // 4` buckets, each emitting up to
four points. Thus the 1,000-point rendering case is the closest to its current
display workload. The other counts explore what happens if reduction is relaxed
or bypassed; millions of stored samples do not imply millions of drawn vertices.

## Fairness and limitations

Full library plots have axes, tick labels, titles, and grids. Their tick layout,
plot area, and typography differ. The custom QPainter and QGraphicsView versions
have only fixed horizontal grid lines, titles, clipping, and traces. Raw OpenGL
has only clipped traces. They are useful lower bounds for a custom renderer,
**not feature-equivalent replacements**. Text, automatic ticks, interaction,
resizing, accessibility, and exporting would add implementation work and cost.

QPainter and QGraphicsView share the same path conversion and drawing routine.
They use pyqtgraph's `arrayToQPath` utility for efficient NumPy-to-Qt conversion;
they do not use its plot/axis/scene machinery. A fully independent replacement
would also need a suitable bulk path conversion implementation.

The raw OpenGL prototype uploads float32 vertices to a VBO and draws five
`GL_LINE_STRIP`s with a minimal shader. Coordinate conversion, allocation, and
upload are included. It requests the machine's default desktop context and uses
GLSL 1.20; this is a Windows prototype, not a tested portable GPU abstraction.
VisPy uses its `gl` line method and a Qt-native canvas with axes and grid visuals.

Matplotlib is measured with full redraws and with blitting. The blit adapter
invalidates its cached background when limits change; keeping old axis labels
would yield a fast but incorrect zoom benchmark.

These are local exploratory measurements, not a universal library ranking.
GPU/driver, window size, DPI, antialiasing, curve width, waveform density, and
concurrent desktop activity affect results. Dense random noise may rasterize
very differently from this smooth signal. There are no confidence intervals,
randomized backend ordering, memory measurements, or sustained acquisition/load
tests. Small differences should not drive a migration decision.

## Replacement boundary

`mainwindow.py` gets the widget from `ui_form.py` and uses `append_values`,
`clear_values`, and `show_all_data`. `form.ui` promotes a QWidget to `PlotWidget`.
Keeping that class and those methods preserves the external application API.

Inside `PlotWidget`, pyqtgraph is intertwined with `_rebuild_plots`,
`_configure_plot`, range synchronization, `_time_range`, curve updates, and
viewport-width lookup. Storage, extraction, and serial transport are already
separate and can stay in place.

A migration should first put drawing behind a small adapter:

```text
canvas.widget                            QWidget to add to the existing layout
canvas.set_series(labels)                rebuild visible panels
canvas.set_x_range(start, end)            synchronize panels
canvas.set_data(label, x, y)              submit already reduced arrays
canvas.plot_width(label)                 preserve the current reduction budget
canvas.x_range_changed(start, end)       signal for user navigation
canvas.clear() / close()                 resource cleanup
```

Keep the toolbar, capture storage, refresh scheduling, and series visibility
in `PlotWidget`. Preserve Y auto-range/manual Y zoom, panel synchronization,
range restoration after hiding a series, time units, and clear/close behavior.
A fast custom renderer without those behaviors is not a completed migration.

For pyqtgraph OpenGL, the smaller experiment is simply to request its OpenGL
viewport before creating `GraphicsLayoutWidget` (or use `useOpenGL(True)` on
that view). This avoids replacing the plotting API. The benchmark does this
only inside its worker processes; production settings remain unchanged.

## Reference documentation

- [pyqtgraph 0.14 configuration](https://pyqtgraph.readthedocs.io/en/pyqtgraph-0.14.0/config_options.html)
- [Qt QGraphicsView](https://doc.qt.io/qt-6/qgraphicsview.html)
- [Matplotlib blitting](https://matplotlib.org/stable/users/explain/animations/blitting.html)
- [VisPy line rendering modes](https://vispy.org/api/vispy.visuals.line.line.html)

The installed pyqtgraph 0.14 source was also checked: `GraphicsLayoutWidget`
inherits from its `GraphicsView`, which inherits Qt's `QGraphicsView`.
`PlotCurveItem` selects its native GL drawing path for a supported OpenGL
viewport; an old `enableExperimental` flag is not required for these curves.
