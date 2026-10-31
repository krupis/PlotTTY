# PlotTTY capture format

Each `.plotty` capture saves four things: timestamp, series label, numeric value,
and original serial text. PlotTTY can reopen the capture or export it as CSV.

To save space, labels are stored once and assigned IDs. Values from the same
timestamp and serial text are grouped together. These records are then compressed
in blocks.

## CSV export

CSV has one row per numeric value, with columns `timestamp`, `label`, `value`,
and `raw_text`. Standard CSV quoting preserves commas, quotes, and newlines.

## Binary layout

This section is for implementing a reader or writer.
Integers and IEEE-754 doubles are little-endian; text is UTF-8. Text lengths count
bytes, not characters.

```text
File  = magic + blocks + end marker
Magic = PLOTTY\x00\x01 (8 bytes; final byte is the format version)
Block = uncompressed size (uint32) + compressed size (uint32) + zlib data
End   = two zero uint32s
```

Each block decompresses to complete records in either of these layouts:

| Record | Fields, in order |
| --- | --- |
| Series | `S` byte, ID (uint32), label length (uint32), label bytes |
| Sample group | `R` byte, timestamp (double), raw-text length (uint32), value count (uint32), raw-text bytes, values |
| Each value in a group | Series ID (uint32), numeric value (double) |

Series IDs start at zero and increase by one. The label identifies the series;
define it before using its ID. Consecutive values with the same timestamp and raw
text share a sample group. Doubles preserve signed zero and non-finite values.

Writers target 256 KiB of uncompressed data per block. Format limits are:

- 16 MiB per record or uncompressed block; 16 MiB + 64 KiB per compressed block.
- 100,000 series definitions per file; 1–1,000 values per sample group.

Readers validate decompressed sizes and zlib stream termination. Missing end
markers, truncated or damaged data, and bytes after the end marker are rejected.
