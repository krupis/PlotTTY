# Large CSV import investigation

Historical investigation: the application now records and loads only `.plotty`
captures. The background loading fix remains in use; CSV compatibility was
removed before release. See [the current capture format](../docs/CAPTURE_FORMAT.md).

Tested on the development machine with
`logs/serial_COM15_115200_20260926_180520_plot.csv` (535,279,596 bytes).
The recording `Įrašas 2026-09-26 200302.mp4` shows the loading counter near six
million records before the reported hang.

The previous import accumulated every `CapturedValue` in a list, then called
`PlotWidget.append_values` once on the GUI thread. Building all raw stores and
downsampling buckets blocked event processing after the parsing progress ended.
It also retained the parsed list while building the plot stores.

The importer now reads batches of at most 1,000 CSV records in a `QThread` and
builds the per-series `Plotter` stores there. The GUI takes ownership only after
the worker has finished and creates the curves without replaying all samples.
Progress counts prepared values, including storage preparation, rather than just
parsed records. Cancellation and errors discard partial stores; the existing
plot is kept until success. Starting an import disconnects live serial capture
to avoid mixing it into the imported time base.

## Verification

Two full-file application runs completed with 6,181,158 values, split evenly
across six series (1,030,193 each). Total run times including a short post-import
wait were 58.2 and 55.5 seconds. GUI adoption took 0.17 and 0.23 seconds.
A 16 ms heartbeat continued throughout; its longest observed interval was
442 ms. This removes the long end-of-load block, but does not guarantee that
every UI frame meets a 16 ms deadline during CPU-intensive imports.

Verified prepared curves and zooming after the full import. A separate raster
render check displayed all six series using a prefix of the same file. OpenGL
framebuffer screenshots were unavailable in the background test window, so no
visual OpenGL validation is claimed. Application checks also covered cancelling
while preserving the existing plot and closing during import without destroying
a running thread.

Run the automated parser, worker, and storage checks with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The import no longer retains the complete parsed CSV, but in-memory bucket
summaries still grow with capture size. This change does not impose a fixed
memory bound on arbitrarily large captures.

## Compression measurement

A streaming gzip level-1 compression measurement of the entire file produced
61,379,319 bytes: 88.5% smaller, taking 4.25 seconds on this machine. Output was
counted and discarded; the original file and recording format were unchanged.
Compression reduces disk usage, but reading the CSV still requires parsing its
decompressed records. A future binary recording format could remove repeated
metadata and avoid decimal text parsing; retaining raw serial text is a separate
storage choice.
