# PlotTTY capture format, version 1

Extension: `.plotty`. All integers and IEEE-754 binary64 numbers are little-endian.
This format stores extracted values losslessly, including the original timestamp,
label, unit, raw text, numeric precision, and value order. Console RX/TX/status
logging remains a separate text `.log` file.

Implementation: `modules/core/binary_logging.py` owns the format, recording
session, reader, and atomic CSV export. `modules/controllers/capture_job.py`
runs loading or export through one cancellable worker. The main window shares
one progress dialog and completion handler for both operations. The core module
has no Qt dependency; changing the UI does not change the file format.

## File layout

The eight-byte magic/version prefix is `50 4c 4f 54 54 59 00 01`
(`PLOTTY`, zero, version 1). Unsupported versions are rejected.

The prefix is followed by blocks. Each block has two unsigned 32-bit integers:
uncompressed byte length, then compressed byte length. The compressed bytes are
a complete zlib stream, including its checksum, produced using compression
level 1. Both lengths equal to zero mark the completed end of the file. No bytes
may follow that marker.

Writers target 256 KiB of uncompressed data per block and never split a record
between blocks. A larger single record is allowed up to 16 MiB. Readers bound
both compressed input and decompressed output sizes, check zlib completion, and
reject bad checksums, unsupported tags, invalid IDs, and truncated records.

## Records within each decompressed block

### Series definition (`S`, byte 0x53)

| Field | Encoding |
| --- | --- |
| Series ID | uint32 |
| Label byte length | uint32 |
| Label | UTF-8 bytes |
| Unit byte length | uint32 |
| Unit | UTF-8 bytes |

Definitions are sequential IDs beginning at zero and persist across blocks.
Each distinct `(label, unit)` pair is defined once; changing a unit produces a
new ID. Version 1 allows at most 100,000 definitions. Plots still group values by
label, as before; exports preserve each value's unit.

### Sample group (`R`, byte 0x52)

| Field | Encoding |
| --- | --- |
| Timestamp | binary64 |
| Raw-text byte length | uint32 |
| Value count | uint32, 1–1000 |
| Raw text | UTF-8 bytes |
| Values, repeated `count` times | uint32 series ID followed by binary64 value |

Consecutive extracted values with matching timestamps and raw text share one
group. The timestamp and raw text are stored once for the group, rather than
once for every value. The group is an encoding optimization, not a claim about
device packet boundaries. Definition changes, periodic flushes, or the maximum
group size may split a group. Every value is preserved in order.

## Recording and export

Numeric values do not pass through decimal formatting when recording or loading.
Blocks are compressed as they fill. The session also flushes pending values once
per second; disconnect flushes the final group/block and writes the end marker.
Flushing publishes data to the file but is not a power-loss durability guarantee.
Readers currently reject unfinished captures (including abrupt termination) with
a clear error instead of silently presenting a partial recording as complete.

CSV export emits `timestamp,label,value,unit,raw_text`, with standard quoting for
commas, quotes, and embedded newlines. It writes a temporary file beside the
destination and replaces the destination only after successful completion. The
source capture is never overwritten. The application loads only `.plotty` files;
CSV is an export format, not a backwards-compatibility path.

## Measurements

On the development machine, the 73,849,376-byte historical capture
`serial_COM15_115200_20260924_213443_plot.csv` produced a 5,296,913-byte `.plotty`
capture: 92.8% smaller. All 841,134 values matched by SHA-256 over timestamp/value
bits and length-prefixed label/unit/raw-text bytes, in order.

Reading plus computing that validation hash took 4.79 s for CSV and 2.37 s for
binary. This is not a measurement of complete GUI import time: building the
downsampling stores is additional work. The binary GUI import took 6.07 s, and
all six series were rendered and exported successfully.

A 120,000-value recording replay in batches of 120 values took 0.420 s for CSV
and 0.118 s for binary, including finalization. Binary writes included periodic
flushes at simulated one-second intervals. Binary batch p95 was 0.112 ms and
maximum 4.85 ms; compression is batched and does not guarantee every write has
identical latency. These are replay measurements, not a new live-device test.

For reproducibility, `benchmarks/capture_format.py` contains a benchmark-only
reader for historical CSV fixtures and reports size, exact field hashes, read
times, and recording costs. It is not used by the application:

```powershell
.venv\Scripts\python.exe benchmarks/capture_format.py path\to\fixture.csv --output logs\new_capture_benchmark
.venv\Scripts\python.exe -m unittest discover -s tests -v
```
