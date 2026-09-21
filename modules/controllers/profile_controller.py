"""Profile persistence controller."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject

from ..core.models import ExtractionRule
from ..core.profiles import AppProfile, load_profile, save_profile


DEFAULT_PROFILE_PATH = Path("profile.json")


class ProfileController(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.profile_path: Path | None = None

    @property
    def default_save_path(self) -> Path:
        return self.profile_path or DEFAULT_PROFILE_PATH

    @property
    def profile_name(self) -> str:
        return self.default_save_path.name

    def load(self, path: str | Path) -> AppProfile:
        profile = load_profile(path)
        self.profile_path = Path(path)
        return profile

    def save(self, path: str | Path, rules: list[ExtractionRule]) -> None:
        profile = AppProfile(
            name=Path(path).stem,
            rules=rules,
        )
        save_profile(profile, path)
        self.profile_path = Path(path)
