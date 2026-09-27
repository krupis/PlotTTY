# Windows builds

Run from the project root.

**Setup** (Python 3.13):

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Generate Qt resources:**

```bat
.venv\Scripts\pyside6-rcc.exe resources.qrc -o rc_resources.py
```

**Qt deploy** (requires Visual Studio 2022 C++ build tools):

```bat
.venv\Scripts\pyside6-deploy.exe -c pysidedeploy.spec --force
```

Output: `dist\PlotTTY.dist\PlotTTY.exe`.

**Package the Qt deploy build into release ZIPs:**

```bat
.venv\Scripts\python.exe package_windows.py
```

**PyInstaller:**

```bat
.venv\Scripts\python.exe -m pip install PyInstaller==6.22.3
.venv\Scripts\python.exe -m PyInstaller --distpath dist/pyinstaller --workpath build/pyinstaller PlotTTY.spec
```

Output: `dist\pyinstaller\PlotTTY\PlotTTY.exe`. Share the entire output folder, including `app`.

## GitHub releases

Push a version tag matching `pyproject.toml`:

```bat
git tag 1.0.0
git push origin 1.0.0
```

GitHub Actions builds and publishes Windows x64, Linux x64, macOS Intel, and macOS Apple Silicon archives. Run **Build release** manually from the Actions tab to test packaging without creating a release.
