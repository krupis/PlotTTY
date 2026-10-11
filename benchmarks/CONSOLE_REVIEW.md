# Further console simplification — 2026-10-11

This review starts from the [full file-backed implementation](CONSOLE_HISTORY.md),
not the original 50,000-line Qt document. Full temporary history, bounded display,
colors, background whole-file search, native selection/copy and frozen browsing
remain. The serial transport files were not modified.

## Changes retained

- Incoming text goes directly to the buffered history file. A dirty flag replaces
  the additional list of pending text/color pairs. The 50 ms timer still batches
  display updates; this does not force a filesystem flush for every message.
- `ConsoleHistory.read()` returns consecutive `(text, RGB color)` segments.
  The widget inserts each segment with its format. Rendering no longer converts
  UTF-8 byte slices into UTF-16 offsets, decodes the complete window again, then
  makes a separate formatting pass. Qt positions the inserted Unicode text.
- Tests using the private history-read API were updated to the single new result
  format; no old API was retained.

The widget changed from 200 to 195 lines and the backend from 125 to 124, including
docstrings and blank lines: **325 to 319 total**. This is a modest code reduction.
The simpler data flow matters more than this line count; no functionality was
removed to obtain a smaller number.

The remaining scrollbar maps the complete file onto the small loaded document.
The sparse index enables seeking without scanning all earlier lines. Color
checkpoints restore sent/status formatting. Search lifecycle code keeps scans off
the GUI thread, replaces interrupted requests, and stops them before clear/close.
These responsibilities account for most remaining code.

## Live conditions

Physical STM32 USB CDC COM15, native Qt `windows`, 1280×720, visible console, five
plotted fields, device time in field 6, file logging, three-second warmup and plot
history reset, pan/zoom every 500 ms. Simulated firmware stream approximately
10,000 records/s / 719 kB/s; firmware was not edited or flashed. Stress searches
the full file, scrolls and copies the loaded document every two seconds.

Clean comparisons ran baseline stress / simplified stress / simplified stress /
baseline stress, each 40 measured seconds, then baseline/simplified normal capture
for 20 seconds each. A rendering-only variant retaining the write buffer was
also tested twice under stress and once normally. No other Qt tests ran alongside
these comparisons. A final 40-second baseline control followed those variants.
Stress histories contain approximately 430,000 lines.

Artifacts, source snapshots and overlay runners are in `tmp/console-review/`.
`compare.py` reproduces the clean baseline/simplified comparison;
`compare_render.py` tests the rendering-only variant. Baselines load the two saved
modules without reverting production files.

## Measurements

All clean comparison captures sustained approximately 10,000 records/s and had
zero missing sequences, zero additional firmware overflows and zero reported
transport errors. This is evidence for these captures, not a guarantee of lossless
operation under arbitrary loads.

Normal capture, p95:

| Measurement | Baseline | Simplified |
|---|---:|---:|
| UI timer lateness | 5.5 ms | 5.2 ms |
| Plot data refresh | 3.37 ms | 3.14 ms |
| Pan/zoom | 8.61 ms | 8.41 ms |
| Console flush | 3.39 ms | 2.38 ms |

Stress capture, p95, two runs each:

| Measurement | Baseline | Simplified | Rendering only |
|---|---:|---:|---:|
| UI timer lateness | 5.0 / 5.2 ms | 6.1 / 6.6 ms | 6.6 / 5.8 ms |
| Plot data refresh | 3.57 / 3.53 ms | 3.62 / 3.58 ms | 3.61 / 3.37 ms |
| Pan/zoom | 11.49 / 11.32 ms | 11.66 / 11.53 ms | 11.55 / 11.01 ms |
| Scroll | 8.28 / 7.15 ms | 5.74 / 5.56 ms | 5.93 / 5.89 ms |
| Copy loaded window | 11.08 / 10.87 ms | 10.97 / 11.30 ms | 10.61 / 11.18 ms |
| Search dispatch | 1.10 / 0.83 ms | 0.73 / 0.62 ms | 0.91 / 1.35 ms |
| Search completion | 1,412 / 1,400 ms | 1,427 / 1,400 ms | 1,450 / 1,389 ms |

Scrolling consistently takes less time with direct segment insertion. Normal
capture performance remains good. Stress has an observed tradeoff: UI lateness
p95 is roughly 1–1.4 ms higher in the paired simplified runs, and pan/zoom p95
is approximately 0.2 ms higher. Plot refresh changes by only about 0.05 ms.
Keeping the write buffer did not consistently remove the UI-lateness difference,
so the data do not establish immediate writes as its cause. The final baseline
control again had zero gaps/overflows, UI lateness p95 4.9 ms, plot refresh
3.49 ms, pan/zoom 11.81 ms, scroll 6.55 ms and search completion 1,413 ms.
That control supports the UI-lateness tradeoff but shows the 0.2 ms paired
pan/zoom difference is within the observed variation across baseline runs;
the tests do not establish a consistent plotting slowdown. This is not a claim
of uniformly faster plotting or unchanged event-loop latency.

The simplified version is retained for its smaller state and formatting path,
faster scrolling, and sustained capture. The small stress timing differences are
reported explicitly. Console flush timing alone is not a total CPU comparison:
history writes moved from `flush()` into the receive path.

Initial exploratory stress runs overlapped other Qt tests or had large scheduling
spikes: baseline UI max 410 ms, simplified max 654 ms with two missing records.
They remain in the artifacts as `baseline-stress` / `candidate-stress`, but are
excluded from the clean comparison table. Their causes were not established;
repeated isolated runs are the basis for the conclusions above.

UI lateness uses the existing rolling 600-tick monitor. Timings are service times,
not frame rates or input-to-screen latency. Sequential live tests are subject to
Windows scheduling and USB batching. Search history size grows through each run.

## Verification

The focused history, console/USB and workspace test modules cover 50 tests,
including sparse index boundaries, split CRLF, Unicode, color restoration,
full-history search, scrolling beyond 50,000 lines, native copy, frozen browsing,
clear and close. Test logs are under `tmp/console-review/`.
