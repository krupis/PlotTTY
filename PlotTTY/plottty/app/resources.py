"""Application resources."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


APP_ICON_PATH = Path(__file__).resolve().parents[2] / "Logo_smaller.png"


def plottty_icon() -> QIcon:
    if APP_ICON_PATH.exists():
        return QIcon(str(APP_ICON_PATH))
    return QIcon()
