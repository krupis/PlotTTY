# This Python file uses the following encoding: utf-8
import sys

# Show startup feedback before importing the plotting and application modules.
if __name__ == "__main__":
    from modules.startup import run

    sys.exit(run())

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QTabBar, QTabWidget, QToolButton, QWidget

from modules.controllers.connection_session import ConnectionState
from modules.widgets.connection_workspace import ConnectionWorkspace
import rc_resources  # noqa: F401


STYLESHEET_PATH = Path(__file__).resolve().parent / "styles" / "application.qss"
APP_NAME = "PlotTTY"
APP_VERSION = "1.0.0"
APP_DISPLAY_NAME = f"{APP_NAME} {APP_VERSION}"
APP_ICON_RESOURCE = ":/icons/Plottty.png"


def apply_application_style(app: QApplication) -> None:
    # Give Qt-drawn controls a palette that matches the dark stylesheet.
    # Fusion keeps their indicators consistent across Windows themes.
    app.setStyle("Fusion")
    palette = app.palette()
    for role, color in {
        QPalette.ColorRole.Window: "#151c20",
        QPalette.ColorRole.WindowText: "#f3f6f7",
        QPalette.ColorRole.Base: "#0f1417",
        QPalette.ColorRole.AlternateBase: "#20292d",
        QPalette.ColorRole.Text: "#f3f6f7",
        QPalette.ColorRole.Button: "#2b363b",
        QPalette.ColorRole.ButtonText: "#f3f6f7",
        QPalette.ColorRole.Light: "#bac5cb",
        QPalette.ColorRole.Mid: "#56636b",
        QPalette.ColorRole.Dark: "#2b363b",
        QPalette.ColorRole.Highlight: "#41ccc3",
        QPalette.ColorRole.HighlightedText: "#102823",
        QPalette.ColorRole.PlaceholderText: "#a5b2ba",
    }.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#858b93"))
    app.setPalette(palette)

    try:
        stylesheet = STYLESHEET_PATH.read_text(encoding="utf-8")
    except OSError:
        app.setStyleSheet("")
        return

    app.setStyleSheet(stylesheet)


class AddConnectionArea(QWidget):
    reserved_width = 44

    def sizeHint(self):
        size = QSize(self.reserved_width, 38)
        return size


class ConnectionTabs(QTabWidget):
    """Keep the add action immediately after the tabs, including during overflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConnectionTabs")
        self.setDocumentMode(True)
        self.tabBar().setObjectName("ConnectionTabBar")
        self.tabBar().setExpanding(False)
        self.tabBar().setDrawBase(False)
        self._add_area = AddConnectionArea(self)
        layout = QHBoxLayout(self._add_area)
        layout.setContentsMargins(8, 0, 4, 0)
        self.add_button = QToolButton(self._add_area)
        self.add_button.setObjectName("AddConnectionButton")
        self.add_button.setText("+")
        self.add_button.setFixedSize(32, 32)
        self.add_button.setAccessibleName("New connection")
        self.add_button.setToolTip("New connection (Ctrl+T)")
        layout.addWidget(self.add_button)
        layout.addStretch()
        self.setCornerWidget(self._add_area, Qt.Corner.TopRightCorner)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_add_area()

    def update_add_area(self):
        tabs_width = sum(self.tabBar().tabRect(index).width() for index in range(self.count()))
        self._add_area.reserved_width = max(44, self.width() - tabs_width)
        self._add_area.updateGeometry()


class MainWindow(QMainWindow):
    """Own connection tabs; each workspace owns its session and captured data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(QIcon(APP_ICON_RESOURCE))
        self.resize(1280, 800)
        self._preferences = QSettings("PlotTTY", "PlotTTY")
        self._next_connection_number = 1
        self._closing = False
        self._waiting_for_workspaces = False
        self.tabs = ConnectionTabs(self)
        self.tabs.setMovable(True)
        self.setCentralWidget(self.tabs)

        self.add_connection_button = self.tabs.add_button
        self.add_connection_button.clicked.connect(self.add_connection)
        self._new_connection_shortcut = QShortcut(QKeySequence("Ctrl+T"), self)
        self._new_connection_shortcut.activated.connect(self.add_connection)
        self._close_connection_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self._close_connection_shortcut.activated.connect(self.close_current_connection)
        self._console_search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self._console_search_shortcut.activated.connect(self.focus_console_search)
        self.add_connection()
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self.restore_geometry)
        self._restore_timer.start(0)
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.close)

    def add_connection(self) -> ConnectionWorkspace:
        workspace = ConnectionWorkspace(self.tabs, name=f"Connection {self._next_connection_number}")
        self._next_connection_number += 1
        workspace.presentationChanged.connect(self._update_tab)
        workspace.closed.connect(self._remove_workspace)
        index = self.tabs.addTab(workspace, workspace.display_name)
        close_button = QToolButton(self.tabs.tabBar())
        close_button.setObjectName("CloseConnectionButton")
        close_button.setText("\u00d7")
        close_button.setFixedSize(22, 22)
        close_button.setAccessibleName("Close connection")
        close_button.setToolTip("Close connection (Ctrl+W)")
        close_button.clicked.connect(lambda: self.close_connection(self.tabs.indexOf(workspace)))
        self.tabs.tabBar().setTabButton(index, QTabBar.ButtonPosition.RightSide, close_button)
        self.tabs.setCurrentIndex(index)
        self._update_tab(workspace)
        return workspace

    def _update_tab(self, workspace: ConnectionWorkspace) -> None:
        index = self.tabs.indexOf(workspace)
        if index < 0:
            return
        state = workspace.session.state
        color = {ConnectionState.CONNECTED: "#85e0b4", ConnectionState.CONNECTING: "#ffd782",
                 ConnectionState.DISCONNECTED: "#bac5cb"}[state]
        self.tabs.setTabText(index, workspace.display_name)
        self.tabs.setTabToolTip(index, f"{workspace.display_name} · {state.value}")
        indicator = QPixmap(12, 12)
        indicator.fill(Qt.GlobalColor.transparent)
        painter = QPainter(indicator)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(3, 3, 6, 6)
        painter.end()
        self.tabs.setTabIcon(index, QIcon(indicator))
        self.tabs.setIconSize(QSize(12, 12))
        self.tabs.update_add_area()

    def close_current_connection(self) -> None:
        self.close_connection(self.tabs.currentIndex())

    def focus_console_search(self) -> None:
        workspace = self.tabs.currentWidget()
        if workspace is not None:
            workspace.focus_console_search()

    def close_connection(self, index: int) -> None:
        workspace = self.tabs.widget(index)
        if workspace is not None:
            workspace.close()

    def _remove_workspace(self, workspace: ConnectionWorkspace) -> None:
        index = self.tabs.indexOf(workspace)
        if index < 0:
            return
        self.tabs.removeTab(index)
        self.tabs.update_add_area()
        workspace.deleteLater()
        if not self.tabs.count():
            if self._closing:
                if self._waiting_for_workspaces:
                    self._close_timer.start(0)
            else:
                self.add_connection()

    def restore_geometry(self) -> None:
        geometry = self._preferences.value("geometry")
        try:
            if geometry:
                self.restoreGeometry(geometry)
        except TypeError:
            self.resize(1280, 800)
        if not any(screen.availableGeometry().intersects(self.frameGeometry()) for screen in QApplication.screens()):
            self.move(QApplication.primaryScreen().availableGeometry().topLeft())

    def closeEvent(self, event) -> None:
        self._restore_timer.stop()
        self._close_timer.stop()
        if not self._closing:
            self._preferences.setValue("geometry", self.saveGeometry())
            self._closing = True
            self.add_connection_button.setEnabled(False)
            self._new_connection_shortcut.setEnabled(False)
        workspaces = [self.tabs.widget(index) for index in range(self.tabs.count())]
        active = self.tabs.currentWidget()
        for workspace in workspaces:
            if workspace is not active:
                workspace.close()
        if active is not None:
            active.close()
        if self.tabs.count():
            self._waiting_for_workspaces = True
            event.ignore()
            return
        super().closeEvent(event)
