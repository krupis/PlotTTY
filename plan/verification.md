# Direction A implementation and verification

Implemented on 2026-09-29. The main layout remains in `form.ui`; regenerate with
`pyside6-uic form.ui -o ui_form.py`. No dependencies or capture/profile formats changed.

## Delivered

- Designer splitters, 220 px series sidebar, top-bar port/baud controls, and console drawer.
- Draft-only rules dialog with Apply/OK/Cancel, generation, row selection, validation, and preserved X references/units.
- Stable arrival-order colors and independent visibility; hidden series continue capturing.
- Exact in-memory latest sample and latest nonempty unit in live/imported stores. Headers retain existing numeric display formatting and identify their latest-sample meaning in the canvas tooltip.
- One scrolling canvas and one existing 33 ms refresh timer; 150 px minimum panels, shared fixed time footer, unchanged bucket reduction, and retained Y adjustments when hiding/showing a series.
- Single-line commands, separate console/history clear actions, quiet footer, optional diagnostics, and explicit `PlotTTY/PlotTTY` layout preferences.

## Baseline and behavior tests

Before edits, all 21 existing unittests passed. Captured synthetic three/six-series
windows at 1280×720 and measured the original current-widget benchmark.
The baseline screenshots used the same deterministic input for both series counts.
Final visual fixtures additionally cover realistic magnitudes, units, long labels,
constant values, and scientific notation; those visual fixtures are not identical
to the simpler baseline signals. Benchmark input and dimensions are identical.

After implementation, all **34 tests pass**:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

The 13 new Qt behavior tests cover draft isolation, Apply/OK/Cancel, generation,
row-specific validation, profile round trips, selection/removal and X references,
stable colors, dynamic named-value discovery, hidden-sample accumulation, exact
latest values and units through loading, console retention and independent clear,
Enter/Send, shared-axis zoom and Y hit testing after scrolling/resizing, empty and
all-hidden states, connection settings, layout restoration, corrupt preferences,
keyboard interaction, recording paths/errors, raw mode, and background load/export.
Serial connection lifecycle and command delivery use a simulated transport.
Existing tests continue exercising recording data and export integrity.

## Visual review

Rendered three, six, and twelve series at 1280×720 and 1600×1000 logical pixels,
using Qt scale factors 1, 1.5, and 2. Inspected representative renders including
scrolled stacks, long labels, absent units, constant/scientific values, expanded
console, connected controls, rules dialog, and advanced settings. The final polish
removes horizontal sidebar scrolling; complete labels remain in tooltips.

Saved representative artifacts:

- [Before: three series](verification/before-3-series.png)
- [Before: six series](verification/before-6-series.png)
- [After: three series](verification/after-3-series.png)
- [After: six series](verification/after-6-series.png)
- [After: twelve series, scrolled](verification/after-12-series-scrolled.png)
- [Rules dialog](verification/rules-dialog.png)
- [Expanded console](verification/console-expanded.png)

## Short performance comparison

macOS 12.7.6, Python 3.13.3, PySide6/Qt 6.9.3; offscreen Qt platform.
Same machine, deterministic input, 1000×900 logical-pixel plot widget, five series,
100,000 raw samples per series, 10 warmups and 15 measured updates per mode.
The current-widget benchmark does not use its `--repeats` option internally.

```sh
QT_QPA_PLATFORM=offscreen python3 benchmarks/plot_backends.py \
  --backends current-widget --frames 15 --repeats 2 --raw-samples 100000 \
  --output /tmp/plottty-ui-final
```

| Run | Operation | Median ms | p95 ms |
| --- | --- | ---: | ---: |
| baseline | refresh | 18.50 | 19.67 |
| baseline | pan_zoom | 18.26 | 20.57 |
| baseline-repeat | refresh | 20.96 | 23.35 |
| baseline-repeat | pan_zoom | 19.85 | 22.96 |
| redesign-repeat | refresh | 20.62 | 24.68 |
| redesign-repeat | pan_zoom | 19.00 | 23.73 |
| redesign-final | refresh | 17.48 | 18.72 |
| redesign-final | pan_zoom | 19.08 | 20.80 |

A first redesign run overlapped other checks and showed much higher timing variance;
it was excluded from this isolated comparison. The original revision was extracted
into a temporary directory and repeated to distinguish machine variability from a
repeatable regression. The isolated original and redesigned runs are close; these
short measurements do not establish a statistically significant speed difference.
Raw timing samples and environment metadata are retained in the adjacent JSON files.

## Limits

All rendering here used Qt's offscreen platform. These are rendering/service times,
not display FPS, and scale-factor renders do not replace inspection on physical
monitors. Real serial hardware, native Windows/macOS window chrome, monitor removal,
and sustained high-rate device input were not available for manual verification.
The baseline did not include a full interactive device walkthrough; behavioral
coverage was completed with controller/Qt tests after implementation.
