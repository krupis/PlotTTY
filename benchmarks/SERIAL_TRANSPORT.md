# Serial worker necessity and STM32 data rate — 2026-10-11

The serial worker is **not required for the measured processing capacity**.
Every tested implementation sustained approximately 10,000 records/s with the
current file-backed console, compact summaries, logging and plotting.

It nevertheless showed better receive reliability during console interactions.
The simpler variants repeatedly had more missing sequences. Production
`serial_transport.py` was therefore left unchanged. This is a measured reason
to retain it for now, not a claim that threading fixes every missing byte or
that the current implementation is the only possible reliable design.

## Comparison

Physical STM32 USB CDC on COM15; native Qt `windows`; 1280×720; visible console;
five plotted fields; field 6 as device time; logging; three-second warmup; plot
history reset after warmup; pan/zoom every 500 ms. Stress also searches the full
file, scrolls and copies the loaded window every two seconds. Firmware was not
edited or flashed. It currently generates simulated AB-channel data.

The initial normal comparison used 20 seconds per implementation. The stress
comparison ran threaded/readyRead/readyRead/threaded, followed by alternative
GUI implementations and another threaded control. Each stress run lasted 60 s.
Temporary source overlays preserved the production implementation. Source
snapshots, results and screenshots are in `tmp/serial-simplification/`.

| Implementation | Source lines | Normal capture gaps | Stress capture gaps | Stress UI lateness p95 |
|---|---:|---:|---:|---:|
| Current serial worker | 183 | 0 | 0 / 2 / 0 | 6.9 / 6.3 / 7.0 ms |
| GUI readyRead, immediate delivery | 110 | 0 | 4 / 5 | 4.6 / 4.6 ms |
| GUI timer, 8 ms polling | 116 | 0 | 7 / 11 | 5.8 / 4.9 ms |
| GUI readyRead, delivery next event-loop turn | 126 | Not separately run | 3 / 10 | 4.2 / 4.2 ms |

All runs received approximately 10,000 records/s, reported zero transport errors,
and added zero firmware queue overflows. Missing sequences included truncated CSV
suffixes. Their location in the firmware USB path, Windows driver or Qt receive
path remains unresolved. A long average or rounded status rate will not reveal
a few missing records among approximately 600,000.

Normal plotting and UI performance were comparable or better with GUI reception:

| Measurement, 20 s | Worker | GUI readyRead |
|---|---:|---:|
| Records/s | 10,000 | 10,001 |
| UI lateness p95 | 5.8 ms | 4.3 ms |
| Plot data refresh p95 | 3.14 ms | 3.18 ms |
| Pan/zoom p95 | 8.83 ms | 8.52 ms |

Under stress, worker pan/zoom p95 was 10.41–10.67 ms in the first two runs;
readyRead was 9.62–10.02 ms. Plot data refresh p95 was 3.55–3.56 ms versus
3.46–3.49 ms. There is no measured processing-performance requirement for the
extra worker machinery. The practical benefit is draining serial I/O while GUI
work temporarily blocks the main event loop; parsing, recording and plotting
still happen on the GUI thread.

The worker does not make GUI work parallel, increase USB bus bandwidth or speed
up number extraction. Its queue, lock, thread ownership, queued writes and close
drain implement acquisition/lifecycle behavior. Removing all of them reduces
code substantially, but the experiment did not reproduce its receive reliability.

These small counts are not sufficient to assign the underlying defect or
guarantee future loss rates. They are sufficient to reject a claim that the
simple replacement demonstrated identical data integrity in these tests.
UI lateness uses the existing rolling 600-tick monitor; timings are service
times, not displayed FPS or input-to-screen latency.

## Firmware's nominal stream rate

The running C configuration uses an 8 MHz HSE, PLL M=4/N=168/P=2, giving 168 MHz
SYSCLK. APB1 is divided by four to 42 MHz; its timer clock is 84 MHz. TIM4 uses
prescaler 83 and period 99:

```text
84,000,000 / (83 + 1) / (99 + 1) = 10,000 interrupts/s
```

When not blanked, the simulated path adds one combined AB record per interrupt.
That means **10,000 records/s**, each containing four electrical values:
voltage A, current A, voltage B and current B. It is not four separate CSV records.
Actual fresh ADC conversion rate was not verified.

The `.ioc` disagrees with this generated C configuration: its TIM4 prescaler is
839 and period 9999, which would produce 10 Hz at the same timer clock. The C
source and measured 100 µs median device interval support the 10 kHz rate used
here. No firmware settings were silently changed to resolve that mismatch.

## CSV bytes per second

The text stream contains eight fields, seven commas and CRLF:

```text
sequence,type,voltageA,currentA,voltageB,currentB,deviceTime,overflow\r\n
```

Nominal payload is `records/s × average encoded record length`. A recorded
example was:

```text
6250059,3,3.306300,20.100000,4.950154,107.145454,625.051024,2670289
```

Including CRLF, this is 69 bytes: 690,000 B/s if every record had that length.
Current B sometimes needs one fewer digit, so the measured mean was 68.9309
bytes, giving **689,309 B/s** at 10 kHz. Raw reception measured **689,300 B/s**.

During the later runs, sequence and device-second fields each gained a digit.
The mean became 70.9309 bytes, giving **709,309 B/s**. A later worker run measured
**709,297 B/s**. Earlier 719 kB/s results had wider counter fields. CSV payload
rate is therefore not a fixed constant even when the record rate is fixed.

The sample shown in the original conversation is 66 bytes including CRLF, or
660,000 B/s at 10 kHz. An example record length should not be treated as the
average indefinitely.

The device uses USB Full Speed and 64-byte endpoints. Full Speed has a gross
12 Mbit/s signaling rate, not a guaranteed 1.5 MB/s application payload rate;
protocol overhead consumes some bandwidth. [ST's USB speed reference](https://www.st.com/content/st_com/en/technical-documents/an4879-introduction-to-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics_asset/chunk-002-topic-an4879-supported-usb-speeds.html).

The 115200 setting is not a physical UART limit for this COM15 stream:
`CDC_Control_FS` does nothing for `CDC_SET_LINE_CODING`. Actual UART 8N1 at
115200 baud would carry at most 11,520 data bytes/s, but this firmware sends USB
CDC packets directly.

## What PlotTTY displays

`ConnectionSession.on_receive` counts `len(data)` when the session processes
received bytes. `update_receive_rate` sums entries in the last one second and
updates the UI every 100 ms. `MainWindow` formats that value as `B/s` with commas.
It is bytes delivered to the session, not USB overhead, records/s, numerical
values/s, file size or a configured baud rate.

In the first matched runs the median displayed values were **689,297 B/s**
(worker) and **689,316 B/s** (GUI readyRead), matching the nominal 689,309 B/s.
Later the worker's median was **709,221 B/s**, with a final label of
**709,351 B/s**, matching the changed nominal 709,309 B/s. Individual labels
fluctuate because USB arrives in batches and timers/GUI delivery are not exact.

The diagnostic now records CSV length statistics and actual emitted UI-rate
values, so these are checked independently of the whole-capture average.

## Implementation check

Qt 6.11.1's Windows implementation schedules further asynchronous I/O before
emitting readyRead. Thus these results do not justify blaming inline parsing
for failure to submit the next read. GUI event-loop servicing is still different
from worker servicing. [Qt's Windows serial implementation](https://raw.githubusercontent.com/qt/qtserialport/v6.11.1/src/serialport/qserialport_win.cpp).

No production transport implementation was replaced by an experimental variant.
Only the developer diagnostic was extended to collect the rate evidence.
