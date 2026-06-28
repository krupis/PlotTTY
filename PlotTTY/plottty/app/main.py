"""Application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import PlotTTYMainWindow
from .resources import plottty_icon
from .style import apply_app_style


def main() -> None:
    app = QApplication(sys.argv)
    app.setWindowIcon(plottty_icon())
    apply_app_style(app)
    window = PlotTTYMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
