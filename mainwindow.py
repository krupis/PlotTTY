# This Python file uses the following encoding: utf-8
import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QMainWindow,
)

# Important:
# You need to run the following command to generate the ui_form.py file
#     pyside6-uic form.ui -o ui_form.py, or
#     pyside2-uic form.ui -o ui_form.py
from ui_form import Ui_MainWindow

from modules.controllers.profile_controller import ProfileController
from modules.controllers.serial_session import SerialSession
from modules.core.models import CapturedValue, ExtractionRule
from modules.core.rule_suggestions import suggest_rules_from_samples
from modules.core.serial_log import parse_plot_log_line
from modules.widgets.console_widget import ConsoleWidget
from modules.widgets.loading_dialog import LoadingDialog
from modules.widgets.rules_table import RulesTable
from modules.widgets.serial_settings_dialog import SerialSettingsDialog
import resources_rc  # noqa: F401


STYLESHEET_PATH = Path(__file__).resolve().parent / "styles" / "application.qss"
APP_NAME = "PlotTTY"
APP_VERSION = "1.0.0"
APP_DISPLAY_NAME = f"{APP_NAME} {APP_VERSION}"
APP_ICON_RESOURCE = ":/icons/Plottty.png"
LOAD_PROGRESS_UPDATE_ROWS = 10_000


def apply_application_style(app: QApplication) -> None:
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

        self.session = SerialSession(self)
        self.profile = ProfileController(self)

        self.plot = self.ui.Plot
        self.console = ConsoleWidget(self.ui.ConsoleTextEdit, self)
        self.rules_table = RulesTable(self.ui.RulesTable, self)

        self._configure_console()
        self._connect_signals()
        self._seed_default_rules()
        self.on_connected_changed(False)

    def _configure_console(self) -> None:
        self.ui.SendCommandTextEdit.setLineWrapMode(self.ui.SendCommandTextEdit.LineWrapMode.NoWrap)
        self.ui.SendCommandTextEdit.setPlaceholderText("Type command and press Enter")
        self.ui.SendCommandTextEdit.installEventFilter(self)

    def _connect_signals(self) -> None:
        self.ui.ConnectButton.clicked.connect(self.on_toggle_serial_connection)
        self.ui.pushButton.clicked.connect(self.on_open_serial_settings)
        self.ui.ClearConsoleButton.clicked.connect(self.on_clear_console_and_plot)
        self.ui.AddRuleButton.clicked.connect(self.on_add_rule)
        self.ui.RemoveRuleButton.clicked.connect(self.on_remove_selected_rules)
        self.ui.GenerateRulesButton.clicked.connect(self.on_generate_rules_from_sample)
        self.rules_table.rulesChanged.connect(self.on_rules_changed)
        self.ui.actionSave_profile.triggered.connect(self.on_save_profile_as)
        self.ui.actionOpen_profile.triggered.connect(self.on_open_profile)
        self.ui.actionLoad_log.triggered.connect(self.on_load_plot_data)
        self.session.connectedChanged.connect(self.on_connected_changed)
        self.session.receivedText.connect(self.console.append_received)
        self.session.sentText.connect(self.console.append_sent)
        self.session.statusText.connect(self.console.append_status)
        self.session.valuesCaptured.connect(self.plot.append_values)
        self.session.receiveRateChanged.connect(self.on_receive_rate_changed)
        self.session.statusChanged.connect(self.statusBar().showMessage)
        self.session.errorOccurred.connect(self.on_serial_error)

    def _seed_default_rules(self) -> None:
        self.set_rules(
            [
                ExtractionRule(label="Auto key/value", mode="auto_key_value"),
            ]
        )

    @Slot()
    def on_rules_changed(self) -> None:
        self.session.set_rules(self.rules_table.rules())

    @Slot()
    def on_open_profile(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(self, "Open Profile", "", "PlotTTY Profile (*.json)")
        if not path:
            return

        try:
            profile = self.profile.load(path)
        except Exception as exc:
            QMessageBox.warning(self, "Open Profile Failed", str(exc))
            return

        self.set_rules(profile.rules or [ExtractionRule(label="Auto key/value", mode="auto_key_value")])
        self.statusBar().showMessage(f"Loaded {self.profile.profile_name}")

    @Slot()
    def on_save_profile_as(self) -> None:
        default_path = str(self.profile.default_save_path)
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Profile",
            default_path,
            "PlotTTY Profile (*.json)",
        )
        if not path:
            return

        try:
            self.profile.save(path, self.rules_table.rules())
        except Exception as exc:
            QMessageBox.warning(self, "Save Profile Failed", str(exc))
            return

        self.statusBar().showMessage(f"Saved {self.profile.profile_name}")

    @Slot()
    def on_load_plot_data(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Load Plot Data",
            str(self.session.log_dir),
            "Plot CSV (*.csv)",
        )
        if not path:
            return

        self.console.clear()
        self.plot.clear_values()
        self.console.append_status(f"[loading plot data from {Path(path).name}]\n")
        self.statusBar().showMessage(f"Loading plot data from {Path(path).name}...")
        self.console.on_flush()
        loading_dialog = LoadingDialog(f"Loading {Path(path).name}", self)
        loading_dialog.start()

        def update_load_progress(row_count: int) -> None:
            message = f"Loaded {row_count:,} rows"
            loading_dialog.set_message(message)
            self.statusBar().showMessage(message)

        try:
            captured_values, row_count = _read_plot_csv(path, update_load_progress)
            loading_dialog.set_message("Rendering plot...")
            self.plot.append_values(captured_values)
            self.plot.show_all_data()
        except Exception as exc:
            loading_dialog.close()
            QMessageBox.warning(self, "Load Plot Data Failed", str(exc))
            return

        loading_dialog.close()
        self.statusBar().showMessage(f"Loaded plot data {Path(path).name}: {row_count:,} rows")

    @Slot()
    def on_generate_rules_from_sample(self) -> None:
        suggestions = suggest_rules_from_samples(self.ui.SampleOutputTextEdit.toPlainText())
        if not suggestions:
            self.statusBar().showMessage("No numeric values found in sample output")
            return

        rules = [suggestion.rule for suggestion in suggestions]
        self.set_rules(rules)
        self.statusBar().showMessage(f"Generated {len(rules)} rule(s) from sample output")

    @Slot()
    def on_open_serial_settings(self) -> None:
        dialog = SerialSettingsDialog(self.session.settings, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        settings = dialog.selected_settings()
        self.session.set_settings(settings)
        self.console.set_line_limit_enabled(settings.console_line_limit)
        self._update_port_status_label(False)

    @Slot()
    def on_add_rule(self) -> None:
        self.rules_table.add_rule()

    @Slot()
    def on_remove_selected_rules(self) -> None:
        self.rules_table.remove_selected_rules()

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self.rules_table.set_rules(rules)

    @Slot()
    def on_toggle_serial_connection(self) -> None:
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
        command = self.ui.SendCommandTextEdit.toPlainText().strip()
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

        self.ui.SendCommandTextEdit.clear()

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.ui.SendCommandTextEdit
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self.on_send_command()
            return True

        return super().eventFilter(watched, event)

    @Slot(bool)
    def on_connected_changed(self, connected: bool) -> None:
        self.ui.ConnectButton.setText("Disconnect" if connected else "Connect")
        self.ui.ConnectButton.setObjectName("red_button" if connected else "green_button")
        self.ui.ConnectButton.style().unpolish(self.ui.ConnectButton)
        self.ui.ConnectButton.style().polish(self.ui.ConnectButton)
        self.ui.pushButton.setEnabled(not connected)
        self.ui.SendCommandTextEdit.setEnabled(connected)
        self._update_port_status_label(connected)

    def _update_port_status_label(self, connected: bool) -> None:
        port = self.session.settings.port or "No port"
        color = "#1f8f3a" if connected else "#c62828"
        self.ui.PortStatusLabel.setText(port)
        self.ui.PortStatusLabel.setStyleSheet(f"color: {color}; font-weight: 600;")

    @Slot(float)
    def on_receive_rate_changed(self, bytes_per_second: float) -> None:
        self.ui.DataReceivedLabel.setText(f"{bytes_per_second:,.0f} B/s")

    def closeEvent(self, event) -> None:
        self.console.on_flush()
        self.session.disconnect_serial()
        super().closeEvent(event)


def _read_plot_csv(
    path: str,
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[list[CapturedValue], int]:
    captured_values = []
    row_count = 0
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as file:
        for line in file:
            captured = parse_plot_log_line(line.rstrip("\r\n"))
            if captured is None:
                continue

            captured_values.append(captured)
            row_count += 1
            if progress_callback is not None and row_count % LOAD_PROGRESS_UPDATE_ROWS == 0:
                progress_callback(row_count)
    return captured_values, row_count


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(QIcon(APP_ICON_RESOURCE))
    apply_application_style(app)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
