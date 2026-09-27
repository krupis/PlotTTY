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
.venv\Scripts\python.exe -m pip install PyInstaller
.venv\Scripts\python.exe -m PyInstaller --distpath dist/pyinstaller --workpath build/pyinstaller PlotTTY.spec
```

Output: `dist\pyinstaller\PlotTTY\PlotTTY.exe`. Share the entire output folder, including `app`.
