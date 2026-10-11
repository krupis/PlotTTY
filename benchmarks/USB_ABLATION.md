# USB change review and removal tests — 2026-10-10

The later [file-backed console simplification](CONSOLE_HISTORY.md) replaces the
50,000-line ring and custom whole-history selection described in this report.
The [subsequent serial transport review](SERIAL_TRANSPORT.md) retests worker
removal with that console and checks the firmware payload against the UI rate.

The console rendering and compact summaries have substantial measured benefits.
Most of the current changes make sense. Removing the serial worker is attractive
for code size, but the longer interaction tests did not establish that removal
as a safe improvement. The worker remains; its duplicate write queue was removed.

This review follows the [initial verification](USB_THROUGHPUT.md). Firmware was
inspected in `E:/Teltonika/ucurrent_v3`, but was neither edited nor flashed.
The connected STM32 is running a **simulated 10 kHz stream**, not a verified
10 kHz rate of fresh ADC conversions. ST-Link appeared as COM14; USB CDC as COM15.

## Conditions and reproducibility

All live comparisons used native Qt `windows`, COM15 at 115200 baud, a 1280×720
window, visible console, five plotted CSV fields (1–5), device time in field 6,
file logging, Fit capture, and a pan/zoom operation every 500 ms. The graph is
scrollable; about two of the five panels are visible at this window size.
No application commands were transmitted. CDC payload throughput exceeds a
physical UART's 115200-baud limit; this port carries USB traffic.

Independent receive-only checks at the beginning and end both measured about
10,000 records/s and 719 kB/s, with zero sequence gaps and zero new device queue
overflows. They do not measure plot or console rendering performance.

Variants loaded the selected original modules from Git HEAD or the initial
working-tree snapshot into separate benchmark processes. Production files were
not repeatedly reverted. The original Git baseline was
`111b8618a2183b0ea1a40fc9789a5823e1839bea`.

Artifacts, snapshots, logs and screenshots are under `tmp/usb-ablation/`.
`run_variant.py`, `sweep.py`, `repeat.py`, `matched.py`, `plot_repeat.py` and
`storage_checks.py` reproduce the variants from these saved sources. They are
temporary investigation tools, not alternate implementations in the app.

The first sweep retained warmup plot history. That exposed records queued while
the port was closed, followed by an idle-time gap on the time axis. Throughput
counts were measured after warmup, but this made live pan/zoom workloads uneven.
The diagnostic now clears plot history after three seconds of warmup. The
`matched-*` results below use that corrected method. Console history and recording
continue through warmup; plot sample counts cover the measured interval.

UI lateness is the existing precise 16 ms timer monitor's rolling 600-tick window,
not USB latency or input-to-screen latency. Stage timings cover the full measured
interval and can overlap. A receive callback's duration also depends on its batch
size, so worker and GUI-thread callback timings must not be compared per call as
equivalent units of work. Device counter widths and OS scheduling change slightly
between live runs; rates just above 10,000 reflect batch boundaries and timer jitter.

## Main removal comparisons

These are 20-second captures after warmup. Two original-worker controls bracketed
the changes. All runs had zero reported transport errors.

| Variant | Records/s | Missing sequences | New device overflows | UI lateness p95 | Console flush p95 |
|---|---:|---:|---:|---:|---:|
| Initial working tree, control 1 | 10,002 | 0 | 0 | 6.2 ms | 4.34 ms |
| Original Git code, current device-time rule | 8,512 | 26,788 | 26,788 | 62.6 ms | 52.92 ms |
| Restore only original console | 9,954 | 7 | 0 | 91.0 ms | 63.93 ms |
| Restore only original bucket summaries | 10,009 | 0 | 0 | 7.4 ms | 4.23 ms |
| Final small simplifications | 10,002 | 0 | 0 | 6.1 ms | 4.21 ms |
| Initial working tree, control 2 | 10,002 | 0 | 0 | 5.6 ms | 4.11 ms |

The old console is consistently much slower. In the earlier two 20-second
removal runs it received 9,557 and 9,547 records/s and caused 6,905 and 6,620 new
device overflows. In the corrected run its worker largely kept acquisition up,
but UI lateness rose to 91 ms. Thus acquisition loss is workload-dependent;
large console service times and poor responsiveness are reproducible.

Merely lowering the old editor's cap was insufficient: 512 and 2,000-block
variants received 9,414 and 9,394 records/s with 11,748 and 12,207 sequence gaps
in the first sweep. Both retained the old `QTextCursor.insertText` rendering path.
A smaller cap alone does not replace the benefit of bounded rendering.

Other first-sweep removals:

| Removal | Records/s | Sequence gaps | UI lateness p95 | Decision |
|---|---:|---:|---:|---|
| Serial worker, original readyRead transport | 10,000 | 0 | 3.8 ms | Investigate with console interactions |
| CapturedValue slots | 10,000 | 0 | 5.5 ms | Keep the one-line memory reduction |
| Missing-Time guard | 9,999 | 0 | 8.1 ms | Keep for correctness |
| Worker replaced by GUI polling at 8 ms | 9,967 | 656 | 5.5 ms | No demonstrated safe simplification |

Those first-sweep UI numbers are descriptive rather than clean pan/zoom
comparisons because of the warmup history issue. A second slots-removal run also
received 10,000 records/s with no gaps; there is no persuasive throughput benefit
from slots alone. The change adds almost no complexity and reduces a captured
value's shallow storage from 152 bytes (object plus shared-key dictionary) to
64 bytes in this Python environment. Referenced strings/floats are excluded.

The missing-Time guard is not a throughput optimization. Without it, a partial
or status record can put host epoch seconds among device-relative timestamps,
violating the ordering required by plot range lookup. Its focused test passes.

## Summary storage and plotting

Fixed-data native benchmarks used five identical deterministic series with
200,000 samples each, a 1000×900 widget, 20 measured frames per repeat, two
repeats, and ten warmup frames. Both implementations returned identical display
point counts. Order was current/original/original/current for each plot style.

| Measurement | Original summaries | Compact summaries |
|---|---:|---:|
| Build five series | 3.65–3.69 s | 1.37–1.42 s |
| Lines, refresh median | 11.01–11.37 ms | 9.82–10.10 ms |
| Lines, pan/zoom median | 11.84–12.01 ms | 10.35–11.13 ms |
| Dots, refresh median | 19.50–19.62 ms | 17.95–18.26 ms |
| Dots, pan/zoom median | 18.34–18.50 ms | 17.14–17.25 ms |
| Retained summary memory, one 200,000-sample series | 18,500,688 bytes | 6,632,688 bytes |

Memory is a separate `tracemalloc` measurement of summaries only, excluding raw
disk storage, the renderer and recordings. It fell about 64%. Build time fell
about 62%. Frame p95 had occasional OS/allocation outliers, especially in the
original implementation; the repeated median ranges give stronger evidence
than a single worst frame. These are synchronous render/navigation timings,
not displayed FPS or live ADC measurements.

In corrected live captures, final pan/zoom p95 was 8.83 ms versus 8.47–9.08 ms
for the initial worker controls. Plot data refresh p95 was 3.15 ms versus
2.89–3.26 ms. Final console flush and event-loop p95 are also inside the control
range. No consistent performance regression was established for the final
small simplifications. An earlier short run had larger isolated stage p95s;
the bracketed rerun did not reproduce that slowdown.

## Console interaction stress and remaining loss

Separate runs searched the full retained history, scrolled away and back, and
copied all history every two seconds, while acquisition, recording and pan/zoom
continued. These operations are additional to the main table's workload.

| Serial implementation | Capture duration | Missing sequences | New device overflows |
|---|---:|---:|---:|
| Initial worker | 40 s / 40 s / 60 s | 0 / 3 / 2 | 0 / 0 / 0 |
| Original GUI readyRead transport | 40 s / 40 s | 2 / 5 | 0 / 0 |
| Simplified GUI transport with disconnect drain | 60 s / 60 s | 8 / 5 | 0 / 0 |
| Final worker with simpler write queue | 60 s | 6 | 0 |

Some failures contained truncated CSV suffixes. Parsing the saved `.plotty`
captures independently confirmed the same gaps, excluding startup backlog gaps.
The diagnostic now records example invalid lines and the sequence, device time,
overflow count and elapsed host time of each gap.

This **is a remaining data-integrity issue**, including in the worker version.
Unchanged device overflow counts distinguish it from sample-queue overflow;
they do not identify whether bytes were lost in firmware USB transmission,
the Windows/Qt receive path or another stage. The experiments do not establish
that removing the worker caused the difference, nor that threading guarantees
zero loss. It remains because the larger removal did not demonstrate a safe
improvement and it independently drains input during GUI pauses.

At 50,000 retained lines, full-history search medians were about 37–39 ms and
copy medians about 16–19 ms. They are measurable synchronous GUI work. Normal
receive-only checks and the final corrected 20-second live capture had no gaps;
that is not a guarantee for arbitrary interaction loads or longer sessions.

## Firmware assessment and the two fields

- Field 6 is the TIM2 device clock in seconds. Sequence field 0 is a record
  number, not seconds. Device time preserves actual timing and shows time gaps.
- Field 7 is cumulative sample-queue overflow. Compare its change during a
  capture; its absolute total also includes time with no host reading. Together
  with sequence gaps it distinguishes queue drops from other missing records.
- Those fields add payload bytes; they provide timing and diagnostics rather
  than increasing throughput. PlotTTY already supports configurable CSV fields
  and requires no new application packet type or capture-format migration.
- Incrementing sequence before the full-queue check makes discarded records
  visible. Keep that change if loss detection is required.
- The queue increase buys burst tolerance, not sustained bandwidth. At 10 kHz,
  usable capacity grew from about 51 ms to 205 ms. Samples plus the parallel
  timestamp/overflow arrays use 72 KiB versus the original samples' 12 KiB:
  an additional 60 KiB. This is material on the configured STM32F407's RAM.
- Faster float formatting and targeted O2 compilation plausibly reduce CPU
  work substantially, particularly in the otherwise unoptimized debug build.
  Their individual effects were not remeasured by reflashing firmware here.
- Both text-record batching and the 1024-byte transmit buffer already existed
  in firmware HEAD. They are not wholly new changes in this diff. Completion
  notification instead of the one-tick sleep is the new scheduling change.
- Setting `usbTxReady` before submission fixes a real completion-interrupt race.
  Removing it would restore a possible permanent streaming stall; keep it.

The host removal comparisons hold all firmware changes constant. They establish
host behavior with the currently flashed firmware, not individual firmware gains.

## Final edits and verification

- Serial writes now use the queued `Signal(bytes)` itself instead of a second
  Python deque and locking/draining logic. The read queue and disconnect drain
  remain, and queued writes are processed before the blocking close request.
- Removed the unused console history-limit setter and one-item fragment lists
  around pending text. Retained the 50,000-line history and bounded view.
- Replaced acquisition tests with focused GUI-pause/drain, failed-open/reopen,
  queued-write and asynchronous write-error checks.
- Extended the diagnostic with console interactions, invalid/gap examples,
  conditions, plotted point counts and the warmup-history correction.

All **94 tests passed** in isolated module processes, with transport tests run
individually to avoid an existing Qt/RTT background-catalog mock-order problem.
An unisolated transport run stalled; no RTT production code was changed.
Test results are in `tmp/usb-ablation/tests/`.

To repeat the maintained diagnostic, leave COM15 free:

```powershell
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --mode raw --duration 15 --output tmp/usb-ablation/raw-repeat
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --duration 20 --output tmp/usb-ablation/live-repeat
.venv/Scripts/python.exe benchmarks/usb_throughput_diagnostics.py --duration 60 --console-interactions --output tmp/usb-ablation/interaction-repeat
```
