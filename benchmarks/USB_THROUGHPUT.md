# USB fixes reapplied to restored PlotTTY — 2026-10-09

For the subsequent independent removal tests, simplifications and remaining
interaction-load loss, see [USB ablation review, 2026-10-10](USB_ABLATION.md).

The working tree was clean before this change. It preserves the existing
`CapturedValue(timestamp, label, value, raw_text)` data model and capture format
version 2. No received-line IDs, console timestamp prefixes, graph/console linking
or capture-format changes from the separate unfinished feature were reintroduced.

Changes: field 6 as device Time in the uCurrent profile; no plot values from
records missing a configured Time field; serial acquisition on a private Qt
thread; 50,000-block console history with a 512-block view and full-history
navigation/search/copy; compact hierarchical numeric plot summaries; slots for
the existing immutable captured-value objects. No new dependencies are required.
No firmware edits or flashing were needed for this reapplication.

## Native device verification

1280×720 window, visible console, five plotted series, file logging, repeated
pan/zoom and three seconds of warmup, using the already-flashed simulated stream:

| Measurement | Restored baseline, 20 s | Fixes, 60 s |
|---|---:|---:|
| Records/s | 8,974 | 9,999.80 |
| Payload B/s | 645,494 | 719,295 |
| Sequence gaps | 18,225 | 0 |
| Counter discontinuities | 0 | 0 |
| New device enqueue overflows | 18,225 | 0 |
| Errors | 0 | 0 |
| UI timer lateness p95 | 30.8 ms | 5.2 ms |
| Console refresh p95 | 34.71 ms | 3.83 ms |
| Pan/zoom p95 | 3.75 ms | 3.88 ms |

The final run received 600,002 records. Its longer duration and changing field
widths mean small pan/zoom differences do not establish a regression. Results
and screenshots are in `tmp/usb-investigation/restored-baseline` and
`tmp/usb-investigation/restored-final-60s`.

Device interval median: 100 µs; p95: 116 µs; min/max: 48/152 µs. These are actual
interrupt timestamps, with jitter. USB arrivals are batched. Wide graph views
use representative points: zoom to Downsample 1:1 to inspect individual samples.
This verifies the current simulated stream, not the ADC's fresh conversion rate.

## Regression checks and reproduction

All 94 tests pass in isolated test-module processes: all 85 existing tests plus
9 focused USB, acquisition, console and summary tests. Captures round-trip in
the unchanged format. Checks cover GUI pauses, pending-input drain on close,
queued writes, failed open/reopen, Unicode, split CRLF, cross-page copying,
frozen history views, extrema, ties and incomplete summary tails.

The combined suite has a pre-existing Qt/RTT fixture-order problem. A read-only
clean-HEAD run reproduced an RTT mock error that opened the real J-Link library
with mock serial number 123. The transport module passes independently. Per-module
logs are in `tmp/usb-investigation/restored-test-results`; no RTT code was changed.

Leave COM15 free and run:

```powershell
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --mode raw --duration 15 --output tmp/usb-investigation/raw-check
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --mode live --duration 60 --output tmp/usb-investigation/live-check
```

The diagnostic is receive-only. It validates the firmware's eight-field CSV
independently of the app data model and sends no application commands. The
console continues to display raw serial text.
