# PlotTTY capture format

The `.plotty` format stores numeric samples and their original serial text.
The reader accepts only version 2; there are no older-format readers or migrations.
All integers and IEEE-754 doubles use little-endian byte order. Text is UTF-8.

## File structure

The file starts with the eight bytes `PLOTTY\x00\x02`. Each subsequent block has
two unsigned 32-bit lengths: the uncompressed size and the compressed size,
followed by a zlib stream containing complete records. Both lengths being zero
marks the end of a completed recording. Trailing bytes and incomplete recordings
are rejected.

Writers target 256 KiB uncompressed blocks, with a 16 MiB maximum record/block
size. Readers allow up to 16 MiB + 64 KiB compressed bytes per block and validate
the decompressed length and stream termination.

## Records

A series definition starts with the byte `S`, followed by an unsigned 32-bit
series ID, an unsigned 32-bit label byte length, and the label bytes. IDs begin
at zero and increase consecutively. Series identity is the label. At most
100,000 series definitions are allowed.

A sample group starts with the byte `R`, followed by a double timestamp, an
unsigned 32-bit raw-text byte length, and an unsigned 32-bit value count. Raw-text
bytes follow, then that many values. Each value consists of an unsigned 32-bit
series ID and a double numeric value. Every referenced series must already be
defined, and groups contain between 1 and 1,000 values.

Consecutive values with the same timestamp and raw text share a group. Numeric
values retain double precision, including signed zero and non-finite values.

## CSV export

CSV contains the columns `timestamp`, `label`, `value`, and `raw_text`, with one
row per numeric value. Standard CSV quoting preserves commas, quotes, and
newlines in labels and raw text.
