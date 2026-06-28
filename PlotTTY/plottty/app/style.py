"""Application-wide visual styling."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QStyleFactory


APP_STYLE = """
QMainWindow {
    background: #d7dde1;
}

QWidget#CentralPage {
    background: #d7dde1;
}

QWidget#TopBar {
    background: #3f4f58;
    border-bottom: 1px solid #2e3b42;
}

QWidget#TopBar QLabel {
    color: #eaf1f4;
    font-weight: 600;
}

QLabel#StatusLabel {
    background: #314047;
    border: 1px solid #52646d;
    border-radius: 4px;
    color: #eaf1f4;
    padding: 6px 10px;
}

QLabel#StatsLabel {
    background: #fbfcfc;
    border: 1px solid #aebbc2;
    border-radius: 4px;
    color: #17242b;
    font-family: Consolas, Menlo, monospace;
    padding: 6px 10px;
}

QMenuBar {
    background: #3f4f58;
    color: #edf3f6;
    padding: 3px 8px;
}

QMenuBar::item {
    background: transparent;
    padding: 5px 10px;
}

QMenuBar::item:selected {
    background: #53656f;
}

QMenu {
    background: #f7f9fa;
    border: 1px solid #b8c3c9;
    color: #17242b;
}

QMenu::item {
    padding: 6px 22px;
}

QMenu::item:selected {
    background: #dcecf7;
}

QTabWidget::pane {
    background: #f4f7f8;
    border: 1px solid #b9c5cb;
    top: -1px;
}

QTabBar::tab {
    background: #e6ecef;
    border: 1px solid #b9c5cb;
    color: #2b3a42;
    padding: 7px 14px;
}

QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #ffffff;
    color: #12212a;
    font-weight: 600;
}

QTabBar::tab:hover {
    background: #f2f6f8;
}

QPushButton {
    background: #eef3f5;
    border: 1px solid #aebbc2;
    border-radius: 4px;
    color: #17242b;
    min-height: 26px;
    padding: 4px 12px;
}

QPushButton:hover {
    background: #ffffff;
    border-color: #7fa8bd;
}

QPushButton:pressed {
    background: #d8e7ee;
}

QPushButton:disabled {
    background: #e2e7ea;
    color: #89959b;
}

QPushButton#ConnectButton {
    background: #1d9bd1;
    border-color: #157fab;
    color: #ffffff;
    font-weight: 700;
}

QPushButton#ConnectButton:hover {
    background: #25aee8;
}

QPushButton#ConnectButton[connected="true"] {
    background: #43515a;
    border-color: #2e3940;
}

QLineEdit,
QComboBox,
QTextEdit,
QPlainTextEdit,
QTableWidget {
    background: #ffffff;
    border: 1px solid #b8c3c9;
    color: #14242c;
    selection-background-color: #1d9bd1;
    selection-color: #ffffff;
}

QLineEdit,
QComboBox {
    border-radius: 3px;
    min-height: 25px;
    padding: 2px 6px;
}

QComboBox::drop-down {
    border: 0;
    width: 22px;
}

QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #9fb0b8;
    color: #14242c;
    outline: 0;
    selection-background-color: #1d9bd1;
    selection-color: #ffffff;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 0 8px;
}

QWidget#SerialConsole {
    background: #fbfcfc;
    border: 1px solid #aab8bf;
}

QPlainTextEdit#SerialConsoleText {
    background: #fbfcfc;
    border: 0;
    color: #101820;
    font-family: Consolas, Menlo, monospace;
    font-size: 12px;
}

QWidget#LivePlot {
    background: #fbfcfc;
    border: 1px solid #aab8bf;
}

QHeaderView::section {
    background: #edf2f4;
    border: 0;
    border-right: 1px solid #c7d0d5;
    border-bottom: 1px solid #c7d0d5;
    color: #23343c;
    font-weight: 600;
    padding: 6px 8px;
}

QTableWidget {
    alternate-background-color: #f5f8f9;
    gridline-color: #d5dde1;
}

QTableWidget::item {
    padding: 4px;
}

QTableWidget QComboBox {
    background: transparent;
    border: 0;
    border-radius: 0;
    min-height: 22px;
    padding: 0 26px 0 6px;
}

QTableWidget QComboBox:hover {
    background: #eef7fb;
}

QTableWidget QComboBox::drop-down {
    border: 0;
    width: 24px;
}

QTableWidget QCheckBox {
    background: transparent;
    color: #14242c;
    spacing: 6px;
    padding-left: 6px;
}

QTableWidget QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #71848d;
    background: #ffffff;
}

QTableWidget QCheckBox::indicator:unchecked {
    background: #ffffff;
    border: 1px solid #71848d;
}

QTableWidget QCheckBox::indicator:checked {
    background: #0f5f73;
    border: 1px solid #083f4d;
}

QTableWidget QCheckBox::indicator:checked:hover {
    background: #137a93;
}

QTableWidget QCheckBox::indicator:unchecked:hover {
    border: 1px solid #0f5f73;
}

QSplitter::handle {
    background: #bac5cb;
}

QSplitter::handle:horizontal {
    width: 5px;
}

QGroupBox {
    border: 1px solid #c0ccd2;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 12px;
    color: #2d3c44;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""


def apply_app_style(app: QApplication) -> None:
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(APP_STYLE)
