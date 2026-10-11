# This Python file uses the following encoding: utf-8
import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtCore import QEvent, QSettings, QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QMainWindow,
    QProgressDialog,
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.controllers.connection_session import ConnectionSession
from modules.core.extraction import clean_label, validate_rules
from modules.controllers.capture_job import CaptureJob
from modules.widgets.console_widget import ConsoleWidget
from modules.widgets.rules_editor import RulesEditor
from modules.widgets.connection_settings_dialog import ConnectionSettingsDialog
from modules.core.rtt_transport import RttSettings
from modules.core.serial_transport import SerialSettings
import rc_resources  # noqa: F401


STYLESHEET_PATH = Path(__file__).resolve().parent / "styles" / "application.qss"
APP_NAME = "PlotTTY"
APP_VERSION = "1.0.0"
APP_DISPLAY_NAME = f"{APP_NAME} {APP_VERSION}"
APP_ICON_RESOURCE = ":/icons/Plottty.png"
MAX_COMMAND_HISTORY = 100


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


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(QIcon(APP_ICON_RESOURCE))

        self._capture_job: CaptureJob | None = None
        self._loading_dialog: QProgressDialog | None = None
        self._close_after_capture = False
        self.session = ConnectionSession(self)
        self._connection_settings = ConnectionSettingsDialog(self.session.settings, self)
        self.profile_path = Path("profile.json")
        self._command_history: list[str] = []
        self._command_history_index = 0
        self._command_draft = ""
        self.ui.CommandEdit.installEventFilter(self)
        self.ui.CommandEdit.setToolTip("Up/Down recalls sent commands. Down past the newest restores your draft.")

        self.plot = self.ui.Plot
        self.console = ConsoleWidget(self.ui.ConsoleTextEdit, self)
        self.console.searchFinished.connect(self.on_console_search_finished)
        self.applied_rules = []

        self._configure_workspace()
        self._export_csv_action = QAction("Export capture as CSV...", self)
        self.ui.menuFile.addAction(self._export_csv_action)
        self.ui.menuFile.addSeparator()
        self._log_to_file_action = QAction("Log to file", self)
        self._log_to_file_action.setCheckable(True)
        self._log_to_file_action.setChecked(self.session.settings.log_to_file)
        self._log_to_file_action.setToolTip("Save connection text and extracted plot values to files when connecting.")
        self.ui.menuFile.addAction(self._log_to_file_action)
        self._connect_signals()
        self.apply_rules([])
        self.statusBar().addPermanentWidget(self.plot.visible_points_label)
        self.statusBar().addPermanentWidget(self.plot.downsample_ratio_label)
        self.set_diagnostics_visible(False)
        self.on_connected_changed(False)
        QTimer.singleShot(0, self.restore_layout)

    def _configure_workspace(self):
        self.ui.MainLayout.removeItem(self.ui.ConnectionLayout)
        self.connection_bar = QWidget(self.ui.centralwidget)
        self.connection_bar.setObjectName("ConnectionBar")
        self.connection_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.connection_bar.setLayout(self.ui.ConnectionLayout)
        self.ui.MainLayout.insertWidget(0, self.connection_bar)
        self.ui.MainLayout.setStretch(1, 1)
        self.ui.ConnectionLayout.setContentsMargins(12, 10, 12, 10)
        self.plot.layout().removeItem(self.plot.controls_layout)
        self.ui.ConnectionLayout.addLayout(self.plot.controls_layout)
        self.ui.ConnectionLayout.setSpacing(12)
        self.connection_type_combo = QComboBox(self.connection_bar)
        self.connection_type_combo.setObjectName("ConnectionTypeCombo")
        self.connection_type_combo.addItem("Serial", self.session.settings.transport)
        self.connection_type_combo.addItem("J-Link RTT", RttSettings())
        self.ui.ConnectionSettingsButton.setText("Settings")
        self.ui.ConnectionSettingsButton.setIcon(QIcon(":/icons/settings.svg"))
        self.ui.ConnectionSettingsButton.setAccessibleName("Connection settings")
        self.ui.ConnectionLayout.insertWidget(0, self.connection_type_combo)
        self.connection_target = QWidget(self.connection_bar)
        self.connection_target.setFixedWidth(220)
        target_layout = QVBoxLayout(self.connection_target)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(2)
        self.connection_target_label = QLabel()
        self.connection_target_label.setObjectName("ConnectionTarget")
        self.connection_details_label = QLabel()
        self.connection_details_label.setObjectName("ConnectionDetails")
        for label in (self.connection_target_label, self.connection_details_label):
            label.setTextFormat(Qt.TextFormat.PlainText)
            target_layout.addWidget(label)
        self.ui.ConnectionLayout.insertWidget(1, self.connection_target)
        self.connection_status = QWidget(self.connection_bar)
        self.connection_status.setFixedWidth(104)
        status_layout = QHBoxLayout(self.connection_status)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        self.connection_status_dot = QLabel()
        self.connection_status_dot.setObjectName("ConnectionStatusDot")
        self.connection_status_dot.setFixedSize(8, 8)
        self.connection_status_label = QLabel("Disconnected")
        self.connection_status_label.setObjectName("ConnectionStatus")
        status_layout.addWidget(self.connection_status_dot)
        status_layout.addWidget(self.connection_status_label)
        self.ui.ConnectionLayout.insertWidget(2, self.connection_status)
        self.plot.controls_layout.setSpacing(8)
        self.ui.MainLayout.setContentsMargins(12, 10, 12, 10)
        self.ui.SeriesLayout.setContentsMargins(16, 14, 16, 14)
        self.ui.SeriesLayout.setSpacing(12)
        self.ui.SeriesSidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.ui.ConsolePanel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.ui.ConsoleLayout.setContentsMargins(12, 14, 12, 12)
        self.plot.layout().setContentsMargins(0, 14, 0, 0)
        self.ui.ConsoleLayout.setSpacing(8)
        heading = QLabel("Plot", self.plot)
        heading.setObjectName("PanelHeading")
        self.plot.layout().insertWidget(0, heading)
        self.ui.SearchLayout.setSpacing(8)
        self.ui.SendButton.setProperty("primary", True)
        self.ui.SendButton.setIcon(QIcon(":/icons/send.svg"))
        self.ui.ClearConsoleButton.setIcon(QIcon(":/icons/clear.svg"))
        self.ui.SendButton.style().unpolish(self.ui.SendButton)
        self.ui.SendButton.style().polish(self.ui.SendButton)
        self.ui.WorkspaceLayout.setContentsMargins(0, 0, 0, 0)
        self._console_search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self._recording_label = QLabel("Not recording")
        self._rate_label = QLabel("0 B/s")
        self.statusBar().addWidget(self._recording_label, 1)
        self.statusBar().addPermanentWidget(self._rate_label)
        self.ui.SeriesSidebar.setMinimumWidth(420)
        self.ui.MainSplitter.setSizes([500, 1000])
        self.ui.MainSplitter.setStretchFactor(0, 0)
        self.ui.MainSplitter.setStretchFactor(1, 1)
        self.rules_editor = RulesEditor([], self.ui.SeriesSidebar)
        self.ui.SeriesLayout.addWidget(self.rules_editor, 1)
        self.ui.MainSplitter.configure_panel("Extraction", 0, self.ui.actionSidebar, 500)
        self.ui.WorkspaceSplitter.configure_panel("Console", 1, self.ui.actionConsole, 180)
        self.ui.WorkspaceSplitter.set_panel_expanded(False)
        self.ui.actionSidebar.setChecked(True)
        self._preferences = QSettings("PlotTTY", "PlotTTY")

    @Slot(int)
    def _connection_type_changed(self, index):
        if self.session.is_connected:
            return
        self.session.settings.transport = self.connection_type_combo.itemData(index)
        self._update_connection_target()

    def _update_connection_target(self):
        settings = self.session.settings.transport
        if isinstance(settings, SerialSettings):
            target = settings.port.strip()
            title = target or "No port selected"
            details = f"{settings.baudrate} baud" if target else "Choose a port in Settings"
            ports = self._connection_settings.transport_widgets[SerialSettings].port_combo
            index = ports.findData(settings.port)
            if target and index >= 0:
                description = ports.itemText(index).partition(" — ")[2]
                if description:
                    details += f" · {description}"
        else:
            target = settings.target.strip()
            title = target or "No RTT target selected"
            probe = f"Probe {settings.probe_serial.strip()}" if settings.probe_serial.strip() else "Automatic probe"
            details = f"{probe} · {settings.interface} · RTT channel {settings.up_channel}" if target else "Choose a target in Settings"
        self.connection_target_label.setToolTip(title)
        self.connection_details_label.setToolTip(details)
        self.connection_target.setToolTip(f"{title}\n{details}")
        for label, text in ((self.connection_target_label, title), (self.connection_details_label, details)):
            label.setText(label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, 220))
        self.ui.ConnectButton.setEnabled(bool(target) or self.session.is_connected)

    def focus_console_search(self):
        self.ui.actionConsole.setChecked(True)
        self.ui.SearchEdit.setFocus()
        self.ui.SearchEdit.selectAll()

    def on_console_search_changed(self, text):
        self._update_console_search(text)

    def on_console_search_next(self):
        self._update_console_search(self.ui.SearchEdit.text())

    def on_console_search_previous(self):
        self._update_console_search(self.ui.SearchEdit.text(), backwards=True)

    def _update_console_search(self, text, *, backwards=False):
        self.ui.SearchMatchLabel.setText("…" if text else "")
        self.console.find_text(text, backwards=backwards)

    def on_console_search_finished(self, current, total):
        self.ui.SearchMatchLabel.setText(f"{current}/{total}" if total else "")

    def set_diagnostics_visible(self, visible):
        self.plot.visible_points_label.setVisible(visible)
        self.plot.downsample_ratio_label.setVisible(visible)

    def restore_layout(self):
        settings = self._preferences
        try:
            geometry = settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
            if not any(screen.availableGeometry().intersects(self.frameGeometry()) for screen in QApplication.screens()):
                self.resize(1280, 800)
                self.move(QApplication.primaryScreen().availableGeometry().topLeft())
            for name in ("MainSplitter", "WorkspaceSplitter"):
                state = settings.value(name)
                if state:
                    getattr(self.ui, name).restoreState(state)
            for name, default in (("Console", False), ("Sidebar", True), ("Diagnostics", False)):
                getattr(self.ui, "action" + name).setChecked(settings.value(name, default, type=bool))
            for splitter, action, key, default in (
                (self.ui.MainSplitter, self.ui.actionSidebar, "sidebarWidth", 500),
                (self.ui.WorkspaceSplitter, self.ui.actionConsole, "consoleHeight", 180),
            ):
                splitter.expanded_size = max(80, int(settings.value(key, default)))
                splitter.set_panel_expanded(action.isChecked())
        except (TypeError, ValueError):
            self.resize(1280, 800)

    def _connect_signals(self) -> None:
        """Connect controls and session signals after window setup."""
        self.connection_type_combo.activated.connect(self._connection_type_changed)
        self._connection_settings.accepted.connect(self.on_save_connection_settings)
        self.ui.ConnectButton.clicked.connect(self.on_toggle_connection)
        self.ui.ConnectionSettingsButton.clicked.connect(self.on_open_connection_settings)
        self.ui.ClearConsoleButton.clicked.connect(self.console.clear)
        self.ui.CommandEdit.returnPressed.connect(self.on_send_command)
        self.ui.CommandEdit.textEdited.connect(self.on_command_edited)
        self.ui.SendButton.clicked.connect(self.on_send_command)

        self.ui.SearchEdit.textChanged.connect(self.on_console_search_changed)
        self.ui.SearchEdit.returnPressed.connect(self.on_console_search_next)
        self.ui.SearchNextButton.clicked.connect(self.on_console_search_next)
        self.ui.SearchPreviousButton.clicked.connect(self.on_console_search_previous)
        self._console_search_shortcut.activated.connect(self.focus_console_search)

        self.rules_editor.rulesApplied.connect(self.apply_rules)
        self.plot.clearPlotRequested.connect(self.on_clear_plot)
        self.ui.actionDiagnostics.toggled.connect(self.set_diagnostics_visible)
        self.ui.actionClearCapturedData.triggered.connect(self.on_clear_console_and_plot)
        self.ui.actionSave_profile.triggered.connect(self.on_save_profile_as)
        self.ui.actionOpen_profile.triggered.connect(self.on_open_profile)
        self.ui.actionLoad_log.triggered.connect(self.on_load_log)
        self._export_csv_action.triggered.connect(self.on_export_csv)
        self._log_to_file_action.toggled.connect(self.on_log_to_file_toggled)

        self.session.connectedChanged.connect(self.on_connected_changed)
        self.session.receivedText.connect(self.console.append_received)
        self.session.sentText.connect(self.console.append_sent)
        self.session.consoleText.connect(self.console.append_status)
        self.session.valuesCaptured.connect(self.plot.append_values)
        self.session.receiveRateChanged.connect(self.on_receive_rate_changed)
        self.session.errorOccurred.connect(self.on_transport_error)

    def apply_rules(self, rules):
        validate_rules(rules)
        renamed_series = {
            clean_label(previous.label): clean_label(current.label)
            for previous, current in zip(self.applied_rules, rules)
            # Named values ruleuse the incoming name, not their rule label.
            if previous.method != "named_values" and current.method != "named_values"
        }
        self.plot.update_series_labels(renamed_series)
        self.applied_rules = [replace(rule) for rule in rules]
        self.plot.set_rules(self.applied_rules)
        self.session.set_rules([replace(rule) for rule in self.applied_rules])
        if self.rules_editor.rules_table.rules() == self.applied_rules:
            self.rules_editor.mark_applied()

    @Slot()
    def on_open_profile(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(self, "Open Profile", "", "PlotTTY Profile (*.json)")
        if not path:
            return

        try:
            profile = load_profile(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Profile Failed", str(exc))
            return

        self.rules_editor.rules_table.set_rules(profile.rules)
        self.apply_rules(profile.rules)
        self.profile_path = Path(path)
        self.statusBar().showMessage(f"Loaded {self.profile_path.name}")

    @Slot()
    def on_save_profile_as(self) -> None:
        default_path = str(self.profile_path)
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Profile",
            default_path,
            "PlotTTY Profile (*.json)",
        )
        if not path:
            return

        try:
            save_profile(AppProfile(Path(path).stem, self.applied_rules), path)
        except Exception as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))
            return

        self.profile_path = Path(path)
        self.statusBar().showMessage(f"Saved {self.profile_path.name}")

    @Slot()
    def on_load_log(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Plot Data", str(self.session.log_dir), "PlotTTY capture (*.plotty)",
        )
        if path:
            self._start_capture_job(path)

    @Slot()
    def on_export_csv(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, "Choose capture to export", str(self.session.log_dir), "PlotTTY capture (*.plotty)",
        )
        if not source:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self, "Export capture as CSV", str(Path(source).with_suffix(".csv")), "CSV (*.csv)",
        )
        if destination:
            self._start_capture_job(source, destination)

    def _start_capture_job(self, path: str, destination: str | None = None) -> None:
        if self._capture_job is not None:
            return
        if destination is None:
            self.session.disconnect_device()  # Do not mix live samples into an imported time base.
        job = self._capture_job = CaptureJob(path, destination, parent=self)
        message = f"{'Exporting' if destination else 'Loading'} {Path(path).name}..."
        dialog = self._loading_dialog = QProgressDialog(message, "Cancel", 0, 0, self)
        dialog.setWindowTitle("Export capture" if destination else "Load capture")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        self.ui.actionLoad_log.setEnabled(False)
        self._export_csv_action.setEnabled(False)
        # These signals belong to this job and its temporary progress dialog.
        job.progress.connect(self._on_capture_progress)
        job.finished.connect(self._finish_capture_job)
        dialog.canceled.connect(job.requestInterruption)
        self.statusBar().showMessage(message)
        dialog.show()
        job.start()

    @Slot(int)
    def _on_capture_progress(self, count: int) -> None:
        job = self._capture_job
        if job is not None and not job.isInterruptionRequested():
            verb = "Exported" if job.destination is not None else "Prepared"
            message = f"{verb} {count:,} values"
            self._loading_dialog.setLabelText(message)
            self.statusBar().showMessage(message)

    @Slot()
    def _finish_capture_job(self) -> None:
        job = self._capture_job
        if job is None:
            return
        self._loading_dialog.reset()
        operation = "CSV export" if job.destination is not None else "Log import"
        try:
            if job.error:
                raise RuntimeError(job.error)
            if job.cancelled or self._close_after_capture or (
                job.destination is None and job.isInterruptionRequested()
            ):
                self.statusBar().showMessage(f"{operation} cancelled")
            elif job.destination is not None:
                self.statusBar().showMessage(f"Saved {job.row_count:,} values to {job.destination}")
            else:
                self.plot.replace_series(job.take_series(), job.start_time)
                self.plot.capture_title.setText(job.path.name)
                self.plot.capture_title.setToolTip(str(job.path))
                self.plot.capture_title.show()
                self.console.clear()
                self.console.append_status(f"[loaded plot data from {job.path.name}]\n")
                self.statusBar().showMessage(f"Loaded {job.path.name}: {job.row_count:,} values")
        except Exception as exc:
            self.statusBar().showMessage(f"{operation} failed")
            QMessageBox.warning(self, f"{operation} failed", str(exc))
        finally:
            job.discard_series()
            job.deleteLater()
            self._loading_dialog.deleteLater()
            self._loading_dialog = None
            self._capture_job = None
            self.ui.actionLoad_log.setEnabled(True)
            self._export_csv_action.setEnabled(True)
        if self._close_after_capture:
            self.close()

    @Slot()
    def on_open_connection_settings(self) -> None:
        if not self.session.is_connected:
            self._connection_settings.set_settings(self.session.settings)
            self._connection_settings.show_below(self.ui.ConnectionSettingsButton)

    @Slot(bool)
    def on_log_to_file_toggled(self, enabled: bool) -> None:
        if not self.session.is_connected:
            self.session.settings.log_to_file = enabled

    @Slot()
    def on_save_connection_settings(self) -> None:
        if self.session.is_connected:
            return
        self.session.settings = replace(
            self._connection_settings.selected_settings(),
            log_to_file=self.session.settings.log_to_file,
        )
        index = self.connection_type_combo.currentIndex()
        self.connection_type_combo.setItemData(index, self.session.settings.transport)
        self._update_connection_target()

    @Slot()
    def on_toggle_connection(self) -> None:
        if self.session.is_connected:
            self.session.disconnect_device()
        else:
            try:
                self.session.connect_device()
            except Exception as exc:
                QMessageBox.warning(self, "Connection Failed", str(exc))

    @Slot()
    def on_clear_plot(self) -> None:
        self.plot.clear_values()
        self.session.reset_receive_rate()
        self.statusBar().showMessage("Cleared plot data")

    @Slot()
    def on_clear_console_and_plot(self) -> None:
        self.console.clear()
        self.on_clear_plot()
        self.statusBar().showMessage("Cleared console and plot data")

    @Slot(str)
    def on_transport_error(self, message: str) -> None:
        QMessageBox.warning(self, "Connection Error", message)

    @Slot()
    def on_send_command(self) -> None:
        command = self.ui.CommandEdit.text().strip()
        if not command:
            return

        try:
            self.session.send_command(command)
        except Exception as exc:
            if self.session.is_connected:
                QMessageBox.warning(self, "Send Command Failed", str(exc))
            else:
                self.statusBar().showMessage(str(exc))
            return

        if not self._command_history or self._command_history[-1] != command:
            self._command_history.append(command)
            del self._command_history[:-MAX_COMMAND_HISTORY]
        self._command_history_index = len(self._command_history)
        self._command_draft = ""
        self.ui.CommandEdit.clear()

    @Slot(str)
    def on_command_edited(self, _text: str) -> None:
        self._command_history_index = len(self._command_history)

    def eventFilter(self, watched, event):
        if (watched is self.ui.CommandEdit and event.type() == QEvent.Type.KeyPress
                and event.modifiers() == Qt.KeyboardModifier.NoModifier
                and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self._command_history):
            if self._command_history_index == len(self._command_history):
                self._command_draft = self.ui.CommandEdit.text()
            step = -1 if event.key() == Qt.Key.Key_Up else 1
            self._command_history_index = max(0, min(len(self._command_history), self._command_history_index + step))
            self.ui.CommandEdit.setText(self._command_history[self._command_history_index]
                                       if self._command_history_index < len(self._command_history) else self._command_draft)
            return True
        return super().eventFilter(watched, event)

    @Slot(bool)
    def on_connected_changed(self, connected: bool) -> None:
        self.ui.ConnectButton.setText("Disconnect" if connected else "Connect")
        self.ui.ConnectButton.setToolTip("Connected — click to disconnect" if connected else "Disconnected — click to connect")
        self.ui.ConnectionSettingsButton.setEnabled(not connected)
        self._log_to_file_action.setChecked(self.session.settings.log_to_file)
        self._log_to_file_action.setEnabled(not connected)
        self.connection_type_combo.setEnabled(not connected)
        self.ui.ConnectButton.setProperty("connected", connected)
        self.ui.ConnectButton.style().unpolish(self.ui.ConnectButton)
        self.ui.ConnectButton.style().polish(self.ui.ConnectButton)
        self.connection_status_label.setText("Connected" if connected else "Disconnected")
        for widget in (self.connection_status_dot, self.connection_status_label):
            widget.setProperty("connected", connected)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self._update_connection_target()
        if connected:
            self.ui.ConnectButton.setEnabled(True)
            self._connection_settings.reject()
        self.ui.CommandEdit.setEnabled(connected)
        self.ui.SendButton.setEnabled(connected)
        self.update_recording_status()

    def update_recording_status(self):
        self.statusBar().clearMessage()
        paths = self.session.recording_paths
        recording = self.session.is_connected and self.session.settings.log_to_file
        self._recording_label.setText(f"Recording · {paths[-1].name}" if recording and paths else "Not recording")
        self._recording_label.setToolTip("\n".join(str(path) for path in paths))
        self._recording_label.setProperty("recording", recording and bool(paths))
        self._recording_label.style().unpolish(self._recording_label)
        self._recording_label.style().polish(self._recording_label)

    @Slot(float)
    def on_receive_rate_changed(self, bytes_per_second: float) -> None:
        self._rate_label.setText(f"{bytes_per_second:,.0f} B/s")

    def closeEvent(self, event) -> None:
        if self._capture_job is not None:
            self._close_after_capture = True
            self._capture_job.requestInterruption()
            event.ignore()
            return
        settings = self._preferences
        settings.setValue("geometry", self.saveGeometry())
        for name in ("MainSplitter", "WorkspaceSplitter"):
            settings.setValue(name, getattr(self.ui, name).saveState())
        settings.setValue("consoleHeight", self.ui.WorkspaceSplitter.expanded_size)
        settings.setValue("sidebarWidth", self.ui.MainSplitter.expanded_size)
        for name in ("Console", "Sidebar", "Diagnostics"):
            settings.setValue(name, getattr(self.ui, "action" + name).isChecked())
        self.session.disconnect_device()
        self.console.close()
        self.plot.clear_values()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(APP_ICON_RESOURCE))
    apply_application_style(app)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
