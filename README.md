# PlotTTY

PlotTTY is a Python desktop application for viewing serial data and plotting
extracted values in real time. It uses PySide6 for the interface, serial port
access, and QPainter-based plotting.

## Run from source

From the repository root on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe mainwindow.py
```

Development has been tested with Python 3.13. Dependencies are installed
separately; the virtual environment is not part of the source distribution.

For rendering benchmarks and live-device diagnostics, see
[benchmarks/README.md](benchmarks/README.md). These tools need no dependencies beyond the application requirements.

## Plot workspace

Click **Settings** (the gear button) in the top bar to choose a port and baud rate.
The port selector shows device descriptions beside port names when available
(for example, **COM3 — USB Serial Port**).
The same popover shows all serial settings, encoding, and line ending.
Use **File → Log to file** before connecting to enable or disable saving connection
text and extracted plot values. This option is locked while connected.
The top bar always shows the saved port or RTT target, its key settings, and a separate
dot with **Connected** or **Disconnected** status. Hover over the target summary for full details.
Choose **Save settings**, then **Connect**. Escape or clicking outside discards
unsaved edits; connection settings are locked while connected. Use the **Show** checkbox
in each extraction-table row, then **Apply rules**, to show or hide that rule’s traces. Hidden series continue recording
and retain their colors without taking space in the plot panel.

Use the connection type selector to choose **J-Link RTT** when the target firmware
provides SEGGER RTT. The RTT target field searches the supported-device catalog
from your installed J-Link software. Type any part of a device name to filter matches
or open the dropdown to browse. The catalog loads in the background and is cached
for the app session; custom target names can also be entered. Install the SEGGER J-Link Software and Documentation Pack and
`pylink-square` (included in `requirements.txt`); `JLinkARM.dll` must be available
through `PATH`. In connection settings enter the target device name and, if needed,
the probe serial number, SWD/JTAG interface, speed, control-block address, and RTT
up/down channels. PlotTTY polls the selected up channel into the same console,
extraction, plotting, and recording pipeline as serial, and sends commands on the
selected down channel. Close RTT Viewer, J-Link Commander, and other tools using
the probe before connecting. The J-Link DLL is provided by the separately installed
SEGGER package and is not bundled with PlotTTY.

Transport implementations are separate: `modules/core/serial_transport.py` and
`modules/core/rtt_transport.py` implement the `Transport` interface in
`modules/core/transport.py`. `ConnectionSession.connect_device()` selects and constructs
the backend using its settings class. The connection selector holds its Serial and RTT
settings directly. To add a backend, implement the interface, add it to `TRANSPORT_TYPES`, and
add its settings UI. `ConnectionSession` owns the shared decoding,
extraction, recording, and receive-rate pipeline.
`SerialSettingsWidget` and `RttSettingsWidget` own their transport fields;
`ConnectionSettingsDialog` hosts the selected widget, shared options, and Save/Cancel.
`SerialSettings` and `RttSettings` live with their respective transports;
`ConnectionSettings` holds one selected transport's settings and shared encoding,
line ending, and the logging choice. Backends exchange bytes; the session encodes
console commands. Switching connection type keeps each backend's saved settings
for the current app session.

The session passes its receive and error handlers to the backend constructor.
Backends emit `self.bytesReceived.emit(self, data, timestamp)` and
`self.errorReceived.emit(self, message)`. The transport constructor connects the
supplied handlers directly using Qt queued connections. Each handler receives the
source transport first and ignores events from a disconnected connection.
Backend `close()` calls `super().close()` to stop further signals before releasing
resources. Create a new transport for each connection.
Recording filenames use the connection description, timestamp, and a unique ID.

The app starts with no extraction rules: receiving text does not automatically create plots.
The extraction sidebar contains a sample input and an editable rules table.
Generate rules from a sample or edit the table, then
choose **Apply rules** to update parsing for future samples. The button is teal
for unapplied changes and muted when up to date; inline text appears only for errors. Profiles save
applied rules. Field indices are zero-based (0 is the first field).
The table grows with its rows and scrolls when space is limited, keeping Add/Remove
directly below it. Generate and Apply span the sidebar width, with Apply
anchored at the bottom. Apply is disabled
until the draft differs from the applied rules; reverting edits disables it again.

The **Show** checkbox controls plot visibility and is saved in profiles.
A Named values rule controls all its extracted series; Time rows leave the visibility cell blank.
Hidden series keep collecting data and take no space in the plot panel.

Click a color dot beside a Plot rule to choose its trace color, then **Apply rules**.
Colors update existing traces, plot header labels, and
latest-value labels and are saved in profiles.
Right-click a dot and choose **Automatic color** to return to the default palette.
Time rules have no swatch. A custom color on a **Named values** rule applies to all
series extracted by that rule; automatic mode gives those series separate colors.

Extraction methods use matching names in the UI and in `ExtractionRule.method`
(also the `method` field in saved profiles):

| UI method | Code/profile value |
| --- | --- |
| Named values | `named_values` |
| Delimited values | `delimited_values` |
| Regex pattern | `regex_pattern` |
| First number | `first_number` |

The **Function** column maps to `is_time`: `true` for Time and `false` for Plot.
Profiles use these current names; legacy field names are not supported.

The Graphite & teal theme separates configuration panels from recessed plot and
console surfaces. Teal highlights primary actions and active plot modes; each
series retains its own color. The Connect/Disconnect button also indicates
connection state; baud rate is shown only in connection settings. Auto-scroll
state uses an explicit on/off label.

Each plot header shows the latest captured value, even when viewing
older history. **Fit capture** and **Auto scroll**, on the right of the shared
connection toolbar, control the shared time range. The adjacent capture label
appears only for loaded captures, showing the filename with its full path in a tooltip.
Wheel or drag plots to zoom/pan time; use the Y axis to adjust its range and
double-click it to reset. Larger stacks scroll vertically above a fixed time axis.

Each plot header has a compact waveform badge beside its signal name. Click
**Mode: Analog**, **Mode: Digital**, or **Mode: Dots** to open the visual rendering
picker, with waveform icons and a short explanation of each choice. Choose with
the mouse or arrow keys and Enter; Escape closes the picker without changing mode.
Hover inside a populated plot to see the cursor's X coordinate in elapsed seconds
and Y coordinate on that signal's current axis. The tooltip follows live axis
changes and stays hidden while dragging or outside the plot area.
Analog connects samples with straight lines. Digital holds the previous value
until the next sample timestamp, then draws a vertical edge, suitable for 0/1
signals and other discrete levels. Modes change only the drawing, not recorded values.
Changes take effect immediately and independently for each series. Dots show
sample positions without connecting strokes. Wide views use representative
samples for performance; zoom in to see every individual sample. Graph types
are view settings for the current capture, retained when hiding or renaming
series and reset when clearing data or loading another capture.

Drag the divider at the bottom of the plot upward to open the **Console**, or use
**View → Console**. Drag it down to the bottom edge to collapse the console; the
divider stays available for reopening. Ctrl+F also opens the console and focuses
search. Send commands with Enter or Send. In the command field, **Up/Down** recalls
the last 100 successfully sent commands; consecutive duplicates are skipped.
Down past the newest command restores the unsent draft. Editing a recalled command
starts a new draft. History stays in memory until the app closes, including across
disconnects and console clears. The console's **Clear** button
only clears text; **File → Clear captured data** also clears plotted history,
without deleting recordings. The **View** menu controls the console, sidebar,
and diagnostics (point counts and downsampling). The console keeps the complete
session text in a temporary UTF-8 file and reads a small window as you scroll.
Search scans the complete file in the background; its count reflects the file
when that search started. Native selection, Ctrl+A and Copy apply to the loaded
window. Clear empties the history, and closing the app deletes its temporary file;
enable file logging to keep permanent recordings. See
[console history implementation and measurements](benchmarks/CONSOLE_HISTORY.md).
Window geometry and these layout choices are remembered
separately from profiles; reopening does not reconnect or resume recording.

For redesign screenshots, tests, and benchmark results, see
[the verification notes](plan/verification.md).

## Recording and opening captures

The current uCurrent USB CSV profile reads device seconds from field 6. Field 0
is a sequence counter, not time. When a configured Time rule cannot match an
incomplete/status line, that line stays in the console/raw log without adding
plot values on a different clock. See [USB change review and benchmarks](benchmarks/USB_ABLATION.md)
for the measured rate, loss counters and reproduction commands.

With **Log to file** enabled, PlotTTY saves extracted plot values to compressed
`.plotty` files and serial console text to a separate `.log` file. Captures retain
all numeric values, timestamps, labels, and raw serial text without
reducing numeric precision. Text and plot logs flush every second and on disconnect. Disconnect the device to finish the recording before
opening or exporting it.

Use **File → Load capture…** to open a `.plotty` capture. Loading happens in the
background and can be cancelled. Use **File → Export capture as CSV...** to create
a readable CSV for other tools; exporting also runs in the background. Cancelled
or failed exports do not replace an existing destination file. CSV import is not
supported. CSV columns are `timestamp`, `label`, `value`, and `raw_text`.

Recordings use format version 2. Earlier recording formats are rejected.

The [capture format specification](docs/CAPTURE_FORMAT.md) describes the versioned
binary format. No additional Python dependencies are required.

## Builds and releases

The release workflow in `.github/workflows/release.yml` uses **PyInstaller**
with `PlotTTY.spec`. It creates portable application folders: Windows x64,
Linux x64, macOS Intel, and macOS Apple Silicon. Windows and macOS releases are
ZIPs; Linux releases are tar.gz archives. Each archive has a SHA-256 checksum.
Recipients do not need Python installed. Keep the extracted application and its
supporting files together.

Push a version tag matching `[project].version` in `pyproject.toml` to build and
publish a GitHub release. For example, for version 1.0.0:

```powershell
git tag 1.0.0
git push origin 1.0.0
```

Run **Build release** manually in GitHub Actions to produce build artifacts
without publishing a release.

To reproduce the Windows build locally with Python 3.13:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt PyInstaller==6.22.3
.venv\Scripts\pyside6-rcc.exe resources.qrc -o rc_resources.py
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath dist --workpath build/pyinstaller PlotTTY.spec
```

Run `dist/PlotTTY/PlotTTY.exe` and distribute the complete `dist/PlotTTY` folder,
including `app/`. macOS builds also produce `dist/PlotTTY.app`. Build each
platform on its matching operating system, as the CI matrix does.

## Project files

- `mainwindow.py` starts the application; `modules/` contains its implementation.
- `form.ui` is the editable Qt Designer form; `ui_form.py` is its generated Python
  code, imported by the application. After editing the form, regenerate it with
  `pyside6-uic form.ui -o ui_form.py`.
- `resources.qrc` lists embedded icons; `rc_resources.py` is the generated Python
  resource module. Regenerate it with `pyside6-rcc resources.qrc -o rc_resources.py`.
- `requirements.txt` lists runtime dependencies; `pyproject.toml` holds project
  metadata and the Qt project file list; `PlotTTY.spec` configures packaging.
- `tests/` contains correctness tests; local performance tools are in `benchmarks/`.
  Temporary measurement outputs belong in ignored `tmp/`.
- `docs/` holds technical documentation; `web/` contains the project website;
  `profiles/` contains example extraction profiles.

## Code naming

Use `snake_case` for modules, methods, and instances, and `PascalCase` for classes.
Name objects for their responsibility: `extraction_engine`, `console_controller`,
and `series_store`. Add type annotations to parameters and return values so their
types remain clear away from construction. Keep Qt override names such as
`paintEvent` unchanged.

Keep each module focused on one responsibility. Related data classes and small
private helpers can live beside the main class; separate substantial components
when that makes their responsibilities easier to navigate. Core modules handle
data, controllers coordinate behavior, and widget modules contain UI components.
For example, `SeriesStore` stores plot samples, `ConsoleController` manages an
existing text editor, and `PlotWidget` owns the plot UI.

## License

PlotTTY's original source code is licensed under the [MIT License](LICENSE).
Third-party libraries and assets retain their own licenses. Dependencies installed
separately include their own license texts:

- [PySide6 and Qt](https://doc.qt.io/qtforpython-6/licenses.html): community
  LGPLv3/GPL options, with module-specific and bundled-component terms.
- [NumPy](https://numpy.org/) and [PyLink](https://github.com/square/pylink):
  runtime dependencies with their own license texts.
- [PyInstaller](https://github.com/pyinstaller/pyinstaller): the release build tool.

### Artwork attribution

`icons/Plottty.png` and `icons/Plottty.ico` are the project owner's own artwork.

Combo-box arrows, checkbox indicators, and the loading dialog's busy progress bar
are drawn by Qt and require no external artwork.

### Executable distributions

Publishing these sources does not constitute a license audit of a packaged
executable. Distributing bundled dependencies requires preserving their notices
and meeting their license requirements, including Qt/PySide6's LGPL obligations
when using that licensing option.
Inventory the actual shipped libraries, plugins, and Python runtime and include
their required license texts and notices. Under the LGPL route, also provide
compliant access to corresponding library source and a working way to replace
or relink the libraries and run the modified application. See
[Qt's LGPL guidance](https://www.qt.io/development/open-source-lgpl-obligations).
Verify these requirements against the actual PyInstaller package; this README
alone does not fulfill them.
