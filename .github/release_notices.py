"""Collect licenses and build-specific source links for the portable package."""

from importlib.metadata import distribution
from pathlib import Path
import os
import platform
import shutil
import sys
import sysconfig
import tomllib

from PySide6.QtCore import qVersion
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def notice_packages():
    """Resolve the installed dependencies used by this release build."""
    pending = [Requirement(line) for line in Path("requirements.txt").read_text().splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    pending.append(Requirement("PyInstaller"))
    packages = {}
    visited = set()
    while pending:
        requirement = pending.pop(0)
        name = canonicalize_name(requirement.name)
        extras = frozenset(requirement.extras)
        key = (name, extras)
        if key in visited:
            continue
        visited.add(key)
        package = distribution(name)
        packages[name] = package
        for dependency in package.requires or ():
            child = Requirement(dependency)
            if child.marker is None or any(
                child.marker.evaluate({"extra": extra}) for extra in extras | {""}
            ):
                pending.append(child)
    resolved_packages = [packages[name] for name in sorted(packages)]
    return resolved_packages


def prepare_notices(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("licenses/Qt.txt", destination / "Qt.txt")
    python_license = next(path for path in (
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
    ) if path.is_file())
    shutil.copyfile(python_license, destination / "Python.txt")
    lines = [
        "PlotTTY bundled dependency versions and source access",
        "",
        f"Python {platform.python_version()}",
        f"https://www.python.org/ftp/python/{platform.python_version()}/Python-{platform.python_version()}.tar.xz",
        "",
    ]
    for package in notice_packages():
        name = package.metadata["Name"]
        lines.extend([
            f"{package.metadata['Name']} {package.version}",
            f"https://pypi.org/project/{name}/{package.version}/#files",
            "",
        ])
        # Preserve nested license paths: NumPy also includes its bundled libraries.
        for entry in package.files or ():
            if any(part.lower().startswith(("license", "copying", "notice"))
                   for part in entry.parts):
                target = destination / name / entry
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(package.locate_file(entry), target)

    qt_version = qVersion()
    pyside_version = distribution("PySide6").version
    app_version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    source_ref = os.environ.get("GITHUB_SHA", app_version)
    lines.extend([
        f"Qt {qt_version} (unmodified libraries from the PySide6 wheels)",
        "Corresponding Qt sources (including module build instructions):",
        f"https://download.qt.io/archive/qt/{'.'.join(qt_version.split('.')[:2])}/{qt_version}/single/qt-everywhere-src-{qt_version}.tar.xz",
        "",
        "Corresponding PySide6 and Shiboken sources (both in pyside-setup):",
        f"https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-{pyside_version}-src/pyside-setup-everywhere-src-{pyside_version}.tar.xz",
        "",
        "PlotTTY source and build instructions:",
        f"https://github.com/krupis/QT_PlotTTY/tree/{source_ref}",
        "See THIRD_PARTY_NOTICES.txt for library replacement instructions.",
    ])
    (destination / "BUILD_INFO.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
