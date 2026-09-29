# This Python file uses the following encoding: utf-8
import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtGui import QAction, QColor, QIcon, QPalette, QPixmap
from PySide6.QtCore import QSettings, QTimer, Qt, Slot
from PySide6.QtSerialPort import QSerialPortInfo
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QMainWindow,
    QProgressDialog,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.core.profiles import AppProfile, load_profile, save_profile
from modules.controllers.serial_session import SerialSession
from modules.core.extraction import default_rules, validate_rules
from modules.controllers.capture_job import CaptureJob
from modules.widgets.console_widget import ConsoleWidget
from modules.widgets.rules_dialog import RulesDialog
from modules.widgets.serial_settings_dialog import SerialSettingsDialog, SUPPORTED_BAUD_RATES
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
        QPalette.ColorRole.Window: "#252b32",
        QPalette.ColorRole.WindowText: "#dce3ea",
        QPalette.ColorRole.Base: "#303b47",
        QPalette.ColorRole.AlternateBase: "#262c33",
        QPalette.ColorRole.Text: "#f0f4f8",
        QPalette.ColorRole.Button: "#3a444f",
        QPalette.ColorRole.ButtonText: "#f0f4f8",
        QPalette.ColorRole.Light: "#a6b5c5",
        QPalette.ColorRole.Mid: "#8091a3",
        QPalette.ColorRole.Dark: "#687b8e",
        QPalette.ColorRole.Highlight: "#2e8b57",
        QPalette.ColorRole.HighlightedText: "#ffffff",
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
        self.session = SerialSession(self)
        self.profile_path = Path("profile.json")

        self.plot = self.ui.Plot
        self.console = ConsoleWidget(self.ui.ConsoleTextEdit, self)
        self.applied_rules = []

        self._configure_workspace()
        self._export_csv_action = QAction("Export capture as CSV...", self)
        self.ui.menuFile.addAction(self._export_csv_action)
        self._export_csv_action.triggered.connect(self.on_export_csv)
        self._connect_signals()
        self.apply_rules(default_rules())
        self.statusBar().addPermanentWidget(self.plot.visible_points_label)
        self.statusBar().addPermanentWidget(self.plot.downsample_ratio_label)
        self.set_diagnostics_visible(False)
        self.on_connected_changed(False)
        QTimer.singleShot(0, self.restore_layout)

    def _configure_workspace(self):
        self.ui.CommandEdit.returnPressed.connect(self.on_send_command)
        self.ui.SendButton.clicked.connect(self.on_send_command)
        self.ui.ConsoleToggle.setDefaultAction(self.ui.actionConsole)
        self.ui.actionConsole.toggled.connect(self.set_console_visible)
        self.ui.actionSidebar.toggled.connect(self.ui.SeriesSidebar.setVisible)
        self.ui.actionDiagnostics.toggled.connect(self.set_diagnostics_visible)
        self.ui.actionClearCapturedData.triggered.connect(self.on_clear_console_and_plot)
        self.ui.SeriesList.itemChanged.connect(self._series_visibility_changed)
        self.ui.RefreshPortsButton.clicked.connect(self.refresh_ports)
        self.ui.BaudCombo.addItems([str(value) for value in SUPPORTED_BAUD_RATES])
        self.refresh_ports()
        self.apply_settings(self.session.settings)
        self.ui.PortCombo.currentTextChanged.connect(self._connection_settings_changed)
        self.ui.BaudCombo.currentTextChanged.connect(self._connection_settings_changed)
        self._recording_label = QLabel("Not recording")
        self._rate_label = QLabel("0 B/s")
        self.statusBar().addWidget(self._recording_label, 1)
        self.statusBar().addPermanentWidget(self._rate_label)
        self.ui.MainSplitter.setSizes([220, 1036])
        self.ui.MainSplitter.setCollapsible(0, False)
        self.ui.MainSplitter.setStretchFactor(0, 0)
        self.ui.MainSplitter.setStretchFactor(1, 1)
        self.ui.WorkspaceSplitter.setCollapsible(0, False)
        self.ui.WorkspaceSplitter.setCollapsible(1, False)
        self._console_height = 180
        self.ui.ConsolePanel.hide()
        self.ui.actionSidebar.setChecked(True)
        self._preferences = QSettings("PlotTTY", "PlotTTY")
        self._sidebar_structure = None
        self.rebuild_sidebar()

    def refresh_ports(self):
        selected = self.session.settings.port
        self.ui.PortCombo.blockSignals(True)
        self.ui.PortCombo.clear()
        self.ui.PortCombo.addItem("")
        for port in QSerialPortInfo.availablePorts():
            self.ui.PortCombo.addItem(port.portName())
            self.ui.PortCombo.setItemData(self.ui.PortCombo.count() - 1, port.description(), Qt.ItemDataRole.ToolTipRole)
        if selected and self.ui.PortCombo.findText(selected) < 0:
            self.ui.PortCombo.addItem(selected)
        self.ui.PortCombo.setCurrentText(selected)
        self.ui.PortCombo.blockSignals(False)

    def _connection_settings_changed(self):
        if not self.session.is_connected:
            self.apply_settings(replace(self.session.settings, port=self.ui.PortCombo.currentText(),
                                        baudrate=int(self.ui.BaudCombo.currentText())))

    def apply_settings(self, settings):
        self.session.settings = settings
        for combo, value in ((self.ui.PortCombo, settings.port), (self.ui.BaudCombo, str(settings.baudrate))):
            combo.blockSignals(True)
            if combo.findText(value) < 0:
                combo.addItem(value)
            combo.setCurrentText(value)
            combo.blockSignals(False)

    def rebuild_sidebar(self):
        self.ui.SeriesList.blockSignals(True)
        info = self.plot.series_info()
        structure = [(entry["label"], entry["unit"], entry["color"].name()) for entry in info]
        if structure == self._sidebar_structure:
            for row, entry in enumerate(info):
                self.ui.SeriesList.item(row).setCheckState(Qt.CheckState.Checked if entry["visible"] else Qt.CheckState.Unchecked)
            self.ui.SeriesList.blockSignals(False)
            return
        self._sidebar_structure = structure
        self.ui.SeriesList.clear()
        if not info:
            item = QListWidgetItem("Waiting for series", self.ui.SeriesList)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
        for entry in info:
            text = entry["label"] + (f" ({entry['unit']})" if entry["unit"] else "")
            item = QListWidgetItem(text, self.ui.SeriesList)
            item.setData(Qt.ItemDataRole.UserRole, entry["label"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if entry["visible"] else Qt.CheckState.Unchecked)
            swatch = QPixmap(12, 12)
            swatch.fill(entry["color"])
            item.setIcon(QIcon(swatch))
            item.setToolTip(text)
        self.ui.SeriesList.blockSignals(False)

    def _series_visibility_changed(self, item):
        self.plot.set_series_visible(item.data(Qt.ItemDataRole.UserRole), item.checkState() == Qt.CheckState.Checked)

    def set_console_visible(self, visible):
        if not visible and self.ui.ConsolePanel.isVisible():
            self._console_height = max(80, self.ui.WorkspaceSplitter.sizes()[1])
        self.ui.ConsoleToggle.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
        self.ui.ConsolePanel.setVisible(visible)
        if visible:
            height = self.ui.WorkspaceSplitter.height()
            self.ui.WorkspaceSplitter.setSizes([max(220, height - self._console_height), self._console_height])

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
            self._console_height = max(80, min(int(settings.value("consoleHeight", 180)), 1000))
            for name, default in (("Console", False), ("Sidebar", True), ("Diagnostics", False)):
                getattr(self.ui, "action" + name).setChecked(settings.value(name, default, type=bool))
        except (TypeError, ValueError):
            self.resize(1280, 800)

    def _connect_signals(self) -> None:
        self.ui.ConnectButton.clicked.connect(self.on_toggle_connection)
        self.ui.SettingsButton.clicked.connect(self.on_open_serial_settings)
        self.ui.ClearConsoleButton.clicked.connect(self.console.clear)
        self.ui.EditRulesButton.clicked.connect(self.open_rules_dialog)
        self.ui.actionSave_profile.triggered.connect(self.on_save_profile_as)
        self.ui.actionOpen_profile.triggered.connect(self.on_open_profile)
        self.ui.actionLoad_log.triggered.connect(self.on_load_log)
        self.session.connectedChanged.connect(self.on_connected_changed)
        self.session.receivedText.connect(self.console.append_received)
        self.session.sentText.connect(self.console.append_sent)
        self.session.consoleText.connect(self.console.append_status)
        self.session.valuesCaptured.connect(self.plot.append_values)
        self.session.receiveRateChanged.connect(self.on_receive_rate_changed)
        self.plot.seriesChanged.connect(self.rebuild_sidebar)
        self.session.errorOccurred.connect(self.on_serial_error)

    def apply_rules(self, rules):
        validate_rules(rules)
        self.applied_rules = [replace(rule) for rule in rules]
        self.session.set_rules([replace(rule) for rule in self.applied_rules])

    def open_rules_dialog(self):
        dialog = RulesDialog(self.applied_rules, self)
        dialog.rulesApplied.connect(self.apply_rules)
        dialog.exec()
        dialog.deleteLater()

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
            self.session.disconnect_serial()  # Do not mix live samples into an imported time base.
        job = self._capture_job = CaptureJob(path, destination, parent=self)
        message = f"{'Exporting' if destination else 'Loading'} {Path(path).name}..."
        dialog = self._loading_dialog = QProgressDialog(message, "Cancel", 0, 0, self)
        dialog.setWindowTitle("Export capture" if destination else "Load capture")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        self.ui.actionLoad_log.setEnabled(False)
        self._export_csv_action.setEnabled(False)
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
    def on_open_serial_settings(self) -> None:
        dialog = SerialSettingsDialog(self.session.settings, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.apply_settings(dialog.selected_settings())
        dialog.deleteLater()

    @Slot()
    def on_toggle_connection(self) -> None:
        if self.session.is_connected:
            self.session.disconnect_serial()
        else:
            try:
                self.session.connect_serial()
            except Exception as exc:
                title = "No Port" if not self.session.settings.port else "Connection Failed"
                QMessageBox.warning(self, title, str(exc))

    @Slot()
    def on_clear_console_and_plot(self) -> None:
        self.console.clear()
        self.plot.clear_values()
        self.session.reset_receive_rate()
        self.statusBar().showMessage("Cleared console and plot data")

    @Slot(str)
    def on_serial_error(self, message: str) -> None:
        QMessageBox.warning(self, "Serial Error", message)

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

        self.ui.CommandEdit.clear()

    @Slot(bool)
    def on_connected_changed(self, connected: bool) -> None:
        self.ui.ConnectButton.setText("Disconnect" if connected else "Connect")
        for widget in (self.ui.SettingsButton, self.ui.PortCombo, self.ui.BaudCombo, self.ui.RefreshPortsButton):
            widget.setEnabled(not connected)
        self.ui.CommandEdit.setEnabled(connected)
        self.ui.SendButton.setEnabled(connected)
        self.ui.PortStatusLabel.setText("● Connected" if connected else "● Disconnected")
        self.ui.PortStatusLabel.setProperty("connected", connected)
        self.ui.PortStatusLabel.style().unpolish(self.ui.PortStatusLabel)
        self.ui.PortStatusLabel.style().polish(self.ui.PortStatusLabel)
        self.update_recording_status()

    def update_recording_status(self):
        self.statusBar().clearMessage()
        paths = self.session.recording_paths
        recording = self.session.is_connected and self.session.settings.log_to_file
        self._recording_label.setText(f"Recording · {paths[-1].name}" if recording and paths else "Not recording")
        self._recording_label.setToolTip("\n".join(str(path) for path in paths))

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
        if self.ui.actionConsole.isChecked():
            self._console_height = max(80, self.ui.WorkspaceSplitter.sizes()[1])
        settings.setValue("consoleHeight", self._console_height)
        for name in ("Console", "Sidebar", "Diagnostics"):
            settings.setValue(name, getattr(self.ui, "action" + name).isChecked())
        self.plot.clear_values()
        self.console.flush()
        self.session.disconnect_serial()
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
