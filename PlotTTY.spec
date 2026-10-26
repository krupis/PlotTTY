# -*- mode: python ; coding: utf-8 -*-
import sys
import tomllib
import runpy
from pathlib import Path


notices = runpy.run_path('.github/release_notices.py')['prepare_notices'](
    Path(workpath) / 'licenses'
)
datas = [
    ('styles/application.qss', 'styles'),
    ('LICENSE', '.'),
    ('THIRD_PARTY_NOTICES.txt', '.'),
    (str(notices), 'licenses'),
]

windows_icon = 'icons/Plottty.ico' if sys.platform == 'win32' else None
app_version = tomllib.loads(
    Path('pyproject.toml').read_text(encoding='utf-8')
)['project']['version']


a = Analysis(
    ['mainwindow.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PlotTTY',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=windows_icon,
    contents_directory='app',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PlotTTY',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='PlotTTY.app',
        icon=None,
        bundle_identifier='io.github.krupis.PlotTTY',
        version=app_version,
        info_plist={
            'NSPrincipalClass': 'NSApplication',
        },
    )
