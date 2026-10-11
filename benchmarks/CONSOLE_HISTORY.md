# Smaller console with full file-backed history — 2026-10-10

For the subsequent storage/rendering simplification and its live comparison,
see [the console review, 2026-10-11](CONSOLE_REVIEW.md). Counts and measurements
below describe the implementation before that small follow-up.

The console previously grew from 111 to 332 lines to preserve scrolling, search,
global selection, copying and keyboard navigation across 50,000 retained lines
while loading only a small window into Qt. Clipping the visible viewport alone
does not reduce the work of maintaining the full Qt text document.

The requested replacement keeps the complete session in a temporary UTF-8 text
file, without the former 50,000-line cap. `console_widget.py` is now 200 lines.
The disk index and background search are in the 125-line
`modules/core/console_history.py`. Together these are 325 lines versus 332 before:
the reduction is substantial in the UI file, but modest across the whole
implementation. Full disk history and responsive whole-file search require a
backend; this is not a claim that moving code between files eliminated it.

Removed: the custom ring, per-row objects and color spans in RAM, whole-history
selection tracking, keyboard selection overrides, custom copy/context menu, and
the extra container/layout wrapping the editor. Qt handles selection and copying
for the loaded document. The full-history scrollbar remains, inside the editor.

## Storage and behavior

- The history file contains normalized plain text, including received, sent and
  status text. It exists even with permanent recording disabled.
- A checkpoint stores the byte offset of every 512th line. Scrolling seeks to
  that checkpoint, skips at most 511 lines, and loads roughly 512 lines into Qt.
  It does not read the entire history to draw a window.
- Color changes are indexed separately in compact arrays. They allow sent and
  status colors to be restored when an older section is loaded.
- The full-history search uses an independent read handle and a fixed byte-size
  snapshot. It counts matches and chooses one without retaining every match.
  Query changes cancel the old scan. Clear and close stop the scan before
  truncating or deleting its file.
- Search reads complete UTF-8 line chunks and yields between blocks to avoid
  monopolizing the Python execution time used by GUI painting and acquisition.
- While browsing older text or holding a selection, incoming text continues to
  the file without replacing the displayed document. Scroll the history bar to
  the bottom to resume following new text.
- Ctrl+A, Copy and keyboard selection operate within the loaded window; they
  no longer create selections spanning arbitrary unloaded history. Full-history
  scrolling and search remain. Permanent recording preserves text after exit.

`mainwindow.py` receives asynchronous search counts and closes the history after
disconnect drains its final input. `pyproject.toml` lists the new module for the
Qt project. The old ring and global-selection implementation and its superseded
tests were removed, rather than retained as a second mode.

## Measurements

Native `windows` Qt platform, physical STM32 USB CDC on COM15, 1280×720 window,
visible console, five plotted fields, device time, logging, three seconds of
warmup, plot history reset after warmup, pan/zoom every 500 ms. The firmware was
unchanged and sends simulated data at about 10,000 records/s, not verified fresh
ADC conversions. Artifacts are in `tmp/console-simplification/`.

Normal capture, 20 measured seconds:

| Measurement | Previous ring | File-backed history |
|---|---:|---:|
| Records/s | 10,001 | 10,001 |
| Sequence gaps / new device overflows | 0 / 0 | 0 / 0 |
| UI timer lateness p95 | 6.3 ms | 5.6 ms |
| Console flush p95 | 4.21 ms | 3.42 ms |
| Plot data refresh p95 | 3.28 ms | 3.04 ms |
| Pan/zoom p95 | 9.05 ms | 8.44 ms |

Interaction capture, 40 measured seconds, full-history search plus scrolling and
native copying of the loaded window every two seconds:

| Measurement | Previous ring, two runs | Final file history, two runs |
|---|---:|---:|
| Records/s | 10,000 / 10,001 | 10,001 / 10,001 |
| Sequence gaps / new device overflows | 0 / 0 in both | 0 / 0 in both |
| UI timer lateness p95 | 6.2 / 7.5 ms | 5.5 / 5.0 ms |
| Plot data refresh p95 | 3.33 / 3.49 ms | 3.62 / 3.52 ms |
| Pan/zoom p95 | 9.75 / 9.71 ms | 10.62 / 10.69 ms |
| Search dispatch p95 | 67.05 / 51.92 ms | 0.87 / 0.80 ms |
| Search completion p95 | 67.05 / 51.92 ms | 1,426 / 1,445 ms |
| Scroll p95 | 9.82 / 9.68 ms | 6.64 / 8.48 ms |
| Copy loaded window p95 | 11.74 / 11.32 ms | 10.39 / 14.05 ms |

The final captures retained about 431,900 lines / 30.6 MB of text with only
6,752 bytes of line checkpoints, plus small color-change arrays. The old version
searched only its most recent 50,000 lines. Live input rate, duration, dimensions,
rules and interaction frequency match; the searched history volume differs by
design. Full-file completion takes longer and grows with history size.

**Observed tradeoff:** pan/zoom p95 during full-file search is about 0.9–1.0 ms
higher in both final repeats. Normal capture did not show that slowdown. The
search does about eight times the historical work; these tests do not isolate
storage, thread scheduling and history volume as separate causes. UI event-loop
p95 is lower, and dispatch no longer blocks on a full scan. Do not describe this
as uniformly faster plotting under every workload.

An initial background scan without cooperative yielding produced a severe
105.8 ms pan/zoom p95. It was rejected. Yielding between blocks and avoiding
unneeded match-position conversions reduced final pan/zoom p95 to about 10.6 ms;
the two repeats above verify the final behavior.

UI lateness uses the existing rolling 600-tick monitor, not the entire capture's
maximum or input-to-screen latency. Timings are service times, not displayed FPS.
Zero gaps in these captures do not guarantee zero loss under all interactions.

## Alternatives rejected

Restoring a native 50,000-line document with bulk append and native copy received
only 4,689 records/s in its 20-second interaction run, with 94,109 missing records
and matching device overflows; native copying took about one second. Reducing
that document to 2,000 lines still produced UI lateness p95 of 125.8 ms and 999
device overflows. Neither replaced the bounded-document implementation.

The intermediate 253-line ring version passed its first device test but was
superseded by the requested complete file history. One deque prototype failed
because of stale ring references and is excluded from comparisons. None of these
alternatives remain in production.

## Verification

Focused tests cover preservation beyond 50,000 lines, oldest/newest scrolling,
native copy of the loaded window, frozen views, split CRLF, Unicode, colors,
sparse-index boundaries, literal search and navigation across read chunks,
snapshot isolation, cancelling search, clearing and temporary-file cleanup.

All 97 tests passed in isolated module processes, with transport tests isolated
individually to avoid the existing Qt/RTT mock-order problem. Results are in
`tmp/console-simplification/tests/`.

```powershell
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --duration 20 --output tmp/console-history-normal
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --duration 40 --console-interactions --output tmp/console-history-interactions
```
