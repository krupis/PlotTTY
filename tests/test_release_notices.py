"""Release notices follow the dependencies installed for the build."""
from importlib.metadata import PackageNotFoundError
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import patch


NOTICE_MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / ".github/release_notices.py"))
notice_packages = NOTICE_MODULE["notice_packages"]


class ReleaseNoticesTest(unittest.TestCase):
    def resolve(self, dependencies):
        packages = {
            name: SimpleNamespace(metadata={"Name": name}, requires=requires)
            for name, requires in dependencies.items()
        }

        def installed_distribution(name):
            if name not in packages:
                raise PackageNotFoundError(name)
            return packages[name]

        with patch.object(Path, "read_text", return_value="app\n"), \
                patch.dict(notice_packages.__globals__, distribution=installed_distribution):
            resolved = notice_packages()
        names = [package.metadata["Name"] for package in resolved]
        return names

    def test_only_active_dependencies_are_required_and_cycles_are_deduplicated(self):
        names = self.resolve({
            "app": ["backend[usb]", "six; python_version < '0'"],
            "backend": ["app", "driver; extra == 'usb'", "dev-tool; extra == 'dev'"],
            "driver": None,
            "pyinstaller": [],
        })
        self.assertEqual(names, ["app", "backend", "driver", "pyinstaller"])

    def test_six_is_included_when_required(self):
        names = self.resolve({"app": ["six"], "six": [], "pyinstaller": []})
        self.assertEqual(names, ["app", "pyinstaller", "six"])

    def test_missing_required_dependency_is_an_error(self):
        with self.assertRaises(PackageNotFoundError):
            self.resolve({"app": ["missing"], "pyinstaller": []})
