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

Click the connection summary in the top bar to choose a port and baud rate.
The same popover shows all serial settings, with expandable capture options.
Choose **Save settings**, then **Connect**. Escape or clicking outside discards
unsaved edits; connection settings are locked while connected. Use the series strip above
the plots to show or hide traces; hidden series continue recording and retain their colors.

The extraction sidebar contains a sample input and an editable rules table.
Generate rules from a sample or edit the table, then
choose **Apply rules** to update parsing for future samples. The button is teal
for unapplied changes and muted when up to date; inline text appears only for errors. Profiles save
applied rules. Field indices are zero-based (0 is the first field).
The table grows with its rows and scrolls when space is limited, keeping Add/Remove
directly below it. Generate and Apply span the sidebar width, with Apply
anchored at the bottom. Apply is disabled
until the draft differs from the applied rules; reverting edits disables it again.

Click a color dot beside a Plot rule to choose its trace color, then **Apply rules**.
Colors update both existing traces and the series strip and are saved in profiles.
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

Each plot header shows the latest captured value and unit, even when viewing
older history. **Fit capture** and **Auto scroll**, on the right of the shared
connection toolbar, control the shared time range. The adjacent capture label
appears only for loaded captures, showing the filename with its full path in a tooltip.
Wheel or drag plots to zoom/pan time; use the Y axis to adjust its range and
double-click it to reset. Larger stacks scroll vertically above a fixed time axis.

Drag the divider at the bottom of the plot upward to open the **Console**, or use
**View → Console**. Drag it down to the bottom edge to collapse the console; the
divider stays available for reopening. Ctrl+F also opens the console and focuses
search. Send commands with Enter or Send. The console's **Clear** button
only clears text; **File → Clear captured data** also clears plotted history,
without deleting recordings. The **View** menu controls the console, sidebar,
and diagnostics (point counts and downsampling). The console retains the latest
50,000 lines; file logging preserves the full serial text when enabled. Window geometry and these layout choices are remembered
separately from profiles; reopening does not reconnect or resume recording.

For redesign screenshots, tests, and benchmark results, see
[the verification notes](plan/verification.md).

## Recording and opening captures

With **Log to file** enabled, PlotTTY saves extracted plot values to compressed
`.plotty` files and serial console text to a separate `.log` file. Captures retain
all numeric values, timestamps, labels, units, and raw serial text without
reducing numeric precision. Text and plot logs flush every second and on disconnect. Disconnect the device to finish the recording before
opening or exporting it.

Use **File → Load capture…** to open a `.plotty` capture. Loading happens in the
background and can be cancelled. Use **File → Export capture as CSV...** to create
a readable CSV for other tools; exporting also runs in the background. Cancelled
or failed exports do not replace an existing destination file. CSV import is not
supported.

The [capture format specification](docs/CAPTURE_FORMAT.md) describes the versioned
binary format. No additional Python dependencies are required.

## Windows standalone build

Use Python 3.13 x64, the application dependencies in `.venv`, and Visual Studio
2022 C++ build tools. Qt's deployment tool reads `pysidedeploy.spec` and runs
Nuitka internally:

```powershell
.venv\Scripts\pyside6-rcc.exe resources.qrc -o rc_resources.py
.venv\Scripts\pyside6-deploy.exe -c pysidedeploy.spec --force
```

`--force` accepts the deployment tool's setup prompts. It installs the Nuitka
version specified in the configuration if needed. Run these commands from the
project root. Qt may update the spec's detected paths/modules during deployment.
The icon resource is generated as `rc_resources.py`, following Qt's naming convention.

Run `dist/PlotTTY.dist/PlotTTY.exe`; Python is not needed on the recipient's machine.
The DLLs, plugin folders and stylesheet must remain beside the executable.
Qt uses `deployment/` for temporary build files. Start from a fresh
`dist/PlotTTY.dist` folder when changing dependencies: Qt overlays that directory
and does not remove obsolete files from previous builds.

To prepare a distributable release:

```powershell
.venv\Scripts\python.exe package_windows.py
```

This small packaging helper collects notices into flat text files and creates:

- `dist/PlotTTY-1.0.0-windows-x64.zip`: the application and license notices.
- `dist/PlotTTY-1.0.0-sources.zip`: matching library sources and application source.

The application ZIP has a portable launcher layout:

```text
PlotTTY/
    PlotTTY.exe
    app/
```

Run the top-level `PlotTTY.exe`. The `app` folder contains the actual application,
DLLs, styles, and license notices; keep it beside the launcher. The packaging
helper compiles `launcher.c` with the same Visual Studio C++ tools used for the
application and embeds the PlotTTY icon. No separate Python installation is
needed. Launch arguments are forwarded to the application.

Publish both ZIPs together on the same release page, or send both when sharing
privately. Only the application ZIP needs extracting to run the app. Recordings
are written under `logs` beside the launcher, and any default relative profile
path is also resolved there, even when launching from another directory. Use a
writable folder. These data files/folders may appear after using the application.
The executable is unsigned. Source downloads are cached in `build/release-sources`.
See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) for library replacement and
source-distribution instructions. The helper covers the current dependencies;
review the build report and update it when dependencies change.

## License

PlotTTY's original source code is licensed under the [MIT License](LICENSE).
Third-party libraries and assets retain their own licenses. Dependencies installed
separately include their own license texts:

- [PySide6 and Qt](https://doc.qt.io/qtforpython-6/licenses.html): community
  LGPLv3/GPL options, with module-specific and bundled-component terms.
Optional benchmarks use [pyqtgraph](https://github.com/pyqtgraph/pyqtgraph),
[NumPy](https://numpy.org/), [Matplotlib](https://matplotlib.org/stable/project/license.html),
[VisPy](https://github.com/vispy/vispy/blob/main/LICENSE.txt), and
[PyOpenGL](https://github.com/mcfletch/pyopengl), under their respective licenses.

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
Verify these requirements against the actual package, including Nuitka
`onefile` builds; this README alone does not fulfill them.
