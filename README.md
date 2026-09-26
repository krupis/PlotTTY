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

`icons/arrow-down.svg`, `icons/check.svg`, and `icons/x.svg` use the regular
[Phosphor Icons](https://github.com/phosphor-icons/core) paths, with customized
size and fill color. Copyright (c) 2023 Phosphor Icons. The full MIT license is
in [licenses/Phosphor-Icons-MIT.txt](licenses/Phosphor-Icons-MIT.txt). This
attribution also covers copies embedded in generated Qt resource files.

`icons/Plottty.png` and `icons/Plottty.ico` are the project owner's own artwork.

The loading dialog uses Qt's built-in busy progress bar and requires no external
animation asset.

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
