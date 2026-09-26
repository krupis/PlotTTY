# PlotTTY

PlotTTY is a Python desktop application for viewing serial data and plotting
extracted values in real time. It uses PySide6 for the interface and serial port
access, and pyqtgraph for plotting.

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
[benchmarks/README.md](benchmarks/README.md). Their additional dependencies are
optional and are not needed to run PlotTTY.

## Recording and opening captures

With **Log to file** enabled, PlotTTY saves extracted plot values to compressed
`.plotty` files and serial console text to a separate `.log` file. Captures retain
all numeric values, timestamps, labels, units, and raw serial text without
reducing numeric precision. Disconnect the device to finish the recording before
opening or exporting it.

Use **File → Load plot data** to open a `.plotty` capture. Loading happens in the
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

Publish both ZIPs together on the same release page, or send both when sharing
privately. Only the application ZIP needs extracting to run the app. Recordings
are written under `logs` in the working directory; use a writable folder.
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
- [pyqtgraph](https://github.com/pyqtgraph/pyqtgraph/blob/master/LICENSE.txt): MIT.
- [NumPy](https://numpy.org/doc/stable/license.html): BSD-3-Clause for the main
  project, with additional licenses for bundled components.

Optional benchmarks also use [Matplotlib](https://matplotlib.org/stable/project/license.html),
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
