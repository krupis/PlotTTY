# USB reconnect buffer clearing — 2026-10-11

The first firmware patch discards its sample ring on USB line setup/DTR
assertion, preserving sequence, device time and overflow counters. It was built,
flashed through ST-Link, verified and reset. The user's subsequent screenshot
still showed samples at about 0.44 s before samples at about 70.04 s.

That reset covers the sample ring, but does not remove a USB batch already
submitted or bytes retained in the PC receive path. A direct USB reconnect
check reproduced 31 / 55 / 31 stale leading records after two-second disconnects
with the first patch on the device. Previously, without the firmware patch,
the same test retained approximately 2,060 leading records.

## PlotTTY change

The serial worker now calls `QSerialPort.clear(Input)` immediately after opening
and before starting its receive timer. This clears the pending input and drops
earlier receive operations. Only input is cleared. A failure closes the port
and follows the existing open-error path. Production change: five added lines
in `modules/core/serial_transport.py`, including the explanatory comment.

The already-flashed firmware and this PC-side change cover the two buffers.
Restart PlotTTY to load the changed Python module; reopening a port inside an
already-running older process does not load edited Python code.

Clear is a start-of-capture boundary: data arriving during open/clear can be
discarded. This does not reset or renumber device counters, and does not recover
samples dropped during disconnection. Console history from previous connections
also remains until the user presses Clear.

## Live checks

Artifacts and diagnostic source are under ignored `tmp/reconnect-review/`.

- The direct receive test with PC input clearing had zero stale prefixes and
  zero sequence gaps in its three measured reconnects.
- The actual production `SerialTransport` was tested twice, six captures each,
  with disconnect intervals of 0.2 / 2 / 0.5 / 5 / 2 seconds. All ten measured
  reconnects had zero stale prefixes. All twelve captures had zero malformed
  lines and no transport errors.
- Two captures in the first run and four in the second had a single missing
  record. In the second run those gaps were all in the first delivered batch,
  at 8.4–9.7 ms after open. Their cause is not established; these checks do not
  demonstrate perfectly contiguous acquisition through the startup boundary.
  The diagnostic's stricter zero-gap assertion therefore exits nonzero for
  these runs, although the stale-prefix check succeeds.
- Opening took approximately 4.5–18.4 ms in those captures. No intentional
  startup delay or periodic flushing was introduced.

Matched 20-second native Windows UI captures used COM15, 1280×720, visible
console, five plotted fields, logging, device time field 6, three-second warmup,
plot-history reset, pan/zoom every 500 ms, and console search/scroll/copy every
two seconds. Both baseline and updated versions received approximately 10,002
records/s, with zero sequence gaps and zero additional firmware queue overflows.

| p95 measurement | Before PC clear | After PC clear |
|---|---:|---:|
| UI timer lateness | 17.4 ms | 8.8 ms |
| Plot data refresh | 4.88 ms | 4.33 ms |
| Pan/zoom | 21.35 ms | 14.79 ms |

No slowdown was observed in this comparison. The change executes only during
open; the streaming loop is identical. These variable Windows timings do not
establish that input clearing improves steady-state plotting performance.
UI lateness is the existing rolling monitor, not input-to-screen latency.

Three focused acquisition tests pass, including discarding stale initial bytes,
preserving later input, clear failure, failed open/reopen, queued writes and
disconnect draining. Tests remain distinct from live-device validation.
