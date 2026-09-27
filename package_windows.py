"""Package pyside6-deploy output and a companion corresponding-source ZIP."""

from importlib.metadata import distribution, version
import hashlib
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
import zipfile

from PySide6.QtCore import qVersion

ROOT = Path(__file__).resolve().parent
APP = ROOT / "dist/PlotTTY.dist"
CACHE = ROOT / "build/release-sources"


def build_launcher():
    """Use the same Visual Studio toolchain as pyside6-deploy."""
    import os
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = subprocess.check_output([
        str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"
    ], text=True).strip()
    if not installation:
        raise SystemExit("Install Visual Studio C++ build tools to build the launcher.")
    folder = ROOT / "build/launcher"
    folder.mkdir(parents=True, exist_ok=True)
    # Resource paths use forward slashes to avoid C-style escape sequences.
    (folder / "launcher.rc").write_text(f'1 ICON "{(ROOT / "icons/Plottty.ico").as_posix()}"\n')
    script = folder / "compile.cmd"
    setup = Path(installation) / "VC/Auxiliary/Build/vcvars64.bat"
    script.write_text(f'@echo off\ncall "{setup}" >nul\nif errorlevel 1 exit /b 1\n'
                      'rc /nologo launcher.rc\nif errorlevel 1 exit /b 1\n'
                      f'cl /nologo /O2 /MT /W3 "{ROOT / "launcher.c"}" launcher.res '
                      '/Fe:PlotTTY.exe /link /SUBSYSTEM:WINDOWS user32.lib\n')
    subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=folder, check=True)
    return folder / "PlotTTY.exe"


def download(url, filename=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (filename or url.rsplit("/", 1)[-1])
    if not path.exists():
        print(f"Downloading {path.name}", flush=True)
        partial = path.with_suffix(".partial")
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(path)
    return path


def write_notices(path, entries):
    # Preserve full texts and their origins, without recreating upstream folder trees.
    seen = set()
    with path.open("w", encoding="utf-8") as out:
        for origin, content in entries:
            if content not in seen:
                out.write(f"{origin}\n{'=' * 72}\n{content}\n\n")
                seen.add(content)


def qt_notices(archive):
    with tarfile.open(archive) as source:
        for member in source:
            path = Path(member.name)
            name = path.name.lower()
            if member.isfile() and ("LICENSES" in path.parts or
                    name.startswith(("license", "copying", "copyright", "notice")) or
                    name in ("qt_attribution.json", "ftl.txt", "ofl.txt")):
                yield member.name, source.extractfile(member).read().decode("utf-8", errors="replace")


def main():
    if not (APP / "PlotTTY.exe").is_file():
        raise SystemExit("Run pyside6-deploy -c pysidedeploy.spec first.")
    launcher = build_launcher()
    # Nuitka excludes qpdf via the spec but still copies its unused dependency.
    if not (APP / "PySide6/qt-plugins/imageformats/qpdf.dll").exists():
        (APP / "qt6pdf.dll").unlink(missing_ok=True)
    # These modules cover the shipped Qt DLLs; fail if a later build adds another.
    supported = {"core", "gui", "widgets", "network", "opengl", "openglwidgets", "test", "serialport", "svg"}
    actual = {p.stem.lower()[3:] for p in APP.rglob("*")
              if p.suffix.lower() == ".dll" and p.stem.lower().startswith("qt6")}
    if not actual <= supported:
        raise SystemExit(f"Add corresponding sources/notices for Qt modules: {actual - supported}")
    licenses = APP / "licenses"
    licenses.mkdir(exist_ok=True)
    qt, pyside = qVersion(), version("PySide6")
    urls = [f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{pyside}-src/"
            f"pyside-setup-everywhere-src-{pyside}.tar.xz"]
    urls += [f"https://download.qt.io/official_releases/qt/{qt.rsplit('.', 1)[0]}/{qt}/submodules/"
             f"{name}-everywhere-src-{qt}.tar.xz"
             for name in ("qtbase", "qtserialport", "qtsvg", "qtimageformats")]
    archives = [download(url) for url in urls]
    write_notices(licenses / "Qt-PySide.txt", (entry for archive in archives for entry in qt_notices(archive)))
    packages = ("nuitka",)
    for name in packages:
        package = distribution(name)
        write_notices(licenses / f"{name}.txt", (
            (str(file), package.locate_file(file).read_text(encoding="utf-8"))
            for file in package.files or [] if ".dist-info/licenses/" in str(file)))
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python.txt")
    openssl = ssl.OPENSSL_VERSION.split()[1]
    license_file = download(f"https://raw.githubusercontent.com/openssl/openssl/openssl-{openssl}/LICENSE.txt",
                            f"OpenSSL-{openssl}-LICENSE.txt")
    shutil.copy2(license_file, licenses / "OpenSSL.txt")
    versions = {name: version(name) for name in (*packages, "PySide6", "shiboken6")}
    versions.update(Python=sys.version.split()[0], Qt=qt, OpenSSL=openssl)
    (APP / "VERSIONS.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.txt", APP)
    app_version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    sources = ROOT / f"dist/PlotTTY-{app_version}-sources.zip"
    with zipfile.ZipFile(sources, "w", zipfile.ZIP_DEFLATED) as out:
        for archive in archives:
            out.write(archive, f"libraries/{archive.name}")
        out.writestr("libraries/ORIGINS.txt", "\n".join(urls))
        files = [ROOT / name for name in ("mainwindow.py", "ui_form.py", "rc_resources.py", "resources.qrc",
                 "form.ui", "requirements.txt", "pyproject.toml", "LICENSE", "README.md",
                 "THIRD_PARTY_NOTICES.txt", "package_windows.py", "pysidedeploy.spec", "launcher.c")]
        for folder, pattern in (("modules", "*.py"), ("styles", "*.qss"), ("icons", "Plottty.*")):
            files.extend((ROOT / folder).rglob(pattern))
        for file in files:
            out.write(file, Path("PlotTTY") / file.relative_to(ROOT))
        out.write(APP / "VERSIONS.json", "PlotTTY/VERSIONS.json")
    output = ROOT / f"dist/PlotTTY-{app_version}-windows-x64.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as out:
        out.write(launcher, "PlotTTY/PlotTTY.exe")
        for file in sorted(APP.rglob("*")):
            relative = file.relative_to(APP)
            if (file.is_file() and relative.parts[0] != "logs" and file.name != "profile.json"
                    and not file.name.endswith((".err.txt", ".out.txt"))):
                out.write(file, Path("PlotTTY/app") / file.relative_to(APP))
    for file in (output, sources):
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        file.with_suffix(".zip.sha256").write_text(f"{digest}  {file.name}\n")
        print(f"{file.name}: {file.stat().st_size / 1024**2:.1f} MiB")
    print("Distribute both ZIPs together. See THIRD_PARTY_NOTICES.txt.")


if __name__ == "__main__":
    main()
