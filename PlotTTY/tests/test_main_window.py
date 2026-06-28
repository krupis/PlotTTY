from PySide6.QtWidgets import QApplication

from plottty.app.main_window import PlotTTYMainWindow
from plottty.core.models import ExtractionRule
from plottty.core.serial_transport import SerialSettings
from plottty.widgets.console_widget import ConsoleWidget
from plottty.widgets.extraction_rules_widget import ExtractionRulesWidget


class _FakeTransport:
    def __init__(self):
        self.is_open = True
        self.settings = SerialSettings()
        self.writes: list[str] = []

    def write_text(self, text: str) -> None:
        self.writes.append(text)


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _console_text(widget: ConsoleWidget) -> str:
    widget.flush()
    return widget.text_view.toPlainText()


def test_send_command_echoes_tx_line_without_capturing_values():
    _app()
    window = PlotTTYMainWindow()
    window.transport = _FakeTransport()

    window.send_command("start")

    assert window.transport.writes == ["start"]
    assert _console_text(window.console).splitlines()[-1] == "start"
    assert window.captured_values.rowCount() == 0


def test_console_decodes_bytes_as_text():
    _app()
    widget = ConsoleWidget()

    widget.append("Temp: 23.4\r\nHumidity: 50\n".encode())

    assert _console_text(widget) == "Temp: 23.4\nHumidity: 50\n"


def test_console_keeps_text_across_chunks():
    _app()
    widget = ConsoleWidget()

    widget.append(b"Temp:")
    widget.append(b" 23.4\n")

    assert _console_text(widget) == "Temp: 23.4\n"


def test_console_keeps_long_lines_intact():
    _app()
    widget = ConsoleWidget()

    widget.append(b"1234567890abcdefghijklmnopqrstuvXYZ\nnext")

    assert _console_text(widget).splitlines() == [
        "1234567890abcdefghijklmnopqrstuvXYZ",
        "next",
    ]


def test_received_bytes_are_shown_as_text():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23.4\n")

    assert _console_text(window.console) == "temp=23.4\n"


def test_console_output_can_be_disabled_while_values_still_plot():
    _app()
    window = PlotTTYMainWindow()

    window.console_output_button.click()
    window.handle_received_data(b"temp=23.4\n", received_at=123.0)
    window.captured_values.flush_pending_updates()

    assert window.console_output_button.text() == "Console Off"
    assert _console_text(window.console) == ""
    assert window.captured_values.rowCount() == 1
    assert window.plot._series["temp"].sample_count() == 1


def test_received_values_are_added_to_plot():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23.4\n")
    window.captured_values.flush_pending_updates()

    assert window.captured_values.rowCount() == 1
    assert "temp" in window.plot._series
    assert window.plot._series["temp"].sample_count() == 1


def test_received_line_uses_host_receive_time():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23.4\n", received_at=123.0)
    window.captured_values.flush_pending_updates()

    assert window.captured_values.rowCount() == 1
    x_values, _y_values = window.plot._series["temp"].read_raw_samples(0, 0)
    assert x_values == [0]

    window.handle_received_data(b"temp=23.5\n", received_at=123.25)

    assert window.plot._series["temp"].latest_timestamp() == 0.25


def test_delimited_sequence_column_is_used_as_plot_x_value():
    _app()
    window = PlotTTYMainWindow()
    window.rules.set_rules(
        [
            ExtractionRule(
                label="Sequence",
                mode="delimiter_column",
                sample_counter=True,
                extra_setting="0",
                delimiter=",",
            ),
            ExtractionRule(label="V1", mode="delimiter_column", extra_setting="2", delimiter=","),
        ]
    )
    window._refresh_engine()

    window.handle_received_data(b"100,3,3.30\n101,3,3.31\n", received_at=123.0)

    assert "Sequence" not in window.plot._series
    x_values, y_values = window.plot._series["V1"].read_raw_samples(0, 1)
    assert x_values == [0, 1]
    assert y_values == [3.30, 3.31]


def test_values_table_keeps_latest_value_per_label():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23.4 humidity=51\n", received_at=123.0)
    window.handle_received_data(b"temp=24.5 humidity=52\n", received_at=124.0)
    window.captured_values.flush_pending_updates()

    assert window.captured_values.rowCount() == 2
    assert window.captured_values.item(0, 1).text() == "temp"
    assert window.captured_values.item(0, 2).text() == "24.5"
    assert window.captured_values.item(1, 1).text() == "humidity"
    assert window.captured_values.item(1, 2).text() == "52"


def test_receive_statistics_show_bytes_received_since_last_timer_tick():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23\n")
    window.handle_received_data(b"temp=24\n")
    window._refresh_receive_statistics()

    assert window.stats_label.text() == "16 B/s"


def test_receive_statistics_reset_counter_after_timer_tick():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23\n")
    window._refresh_receive_statistics()
    window._refresh_receive_statistics()

    assert window.stats_label.text() == "0 B/s"


def test_receive_statistics_starts_timer_when_bytes_are_received():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23\n")

    assert window._stats_timer.isActive()


def test_clear_session_resets_receive_statistics():
    _app()
    window = PlotTTYMainWindow()

    window.handle_received_data(b"temp=23\n", received_at=10.0)
    window.handle_received_data(b"temp=24\n", received_at=11.0)
    window.clear_session()

    assert window.stats_label.text() == "0 B/s"


def test_plot_keeps_raw_timestamp_jitter_visible():
    _app()
    window = PlotTTYMainWindow()

    jittered_times = [1.0, 1.05, 1.10, 1.19, 1.215]
    for index, timestamp in enumerate(jittered_times):
        values = window.engine.extract(f"temp={index}", timestamp=timestamp)
        window.plot.append_values(values)

    x_values, _y_values = window.plot._series["temp"].read_raw_samples(0, 1)
    intervals = [x_values[index + 1] - x_values[index] for index in range(len(x_values) - 1)]

    assert max(intervals) - min(intervals) > 0.05


def test_plot_manual_x_range_disables_auto_scroll():
    _app()
    window = PlotTTYMainWindow()

    values = window.engine.extract("temp=1", timestamp=1.0)
    window.plot.append_values(values)
    window.plot._refresh_pending_data()

    window.plot._plots["temp"].setXRange(0, 1, padding=0)

    assert not window.plot.auto_scroll_button.isChecked()


def test_plot_keeps_history_outside_live_window():
    _app()
    window = PlotTTYMainWindow()

    for index in range(25):
        values = window.engine.extract(f"temp={index}", timestamp=float(index))
        window.plot.append_values(values)

    window.plot._refresh_pending_data()

    points = window.plot._series["temp"]
    assert points.count_visible_samples(0, 0) == 1
    assert points.latest_timestamp() == 24


def test_plot_auto_scroll_off_shows_full_history():
    _app()
    window = PlotTTYMainWindow()

    for index in range(25):
        values = window.engine.extract(f"temp={index}", timestamp=float(index))
        window.plot.append_values(values)

    window.plot._refresh_pending_data()
    window.plot.auto_scroll_button.click()

    start_time, end_time = window.plot._plots["temp"].viewRange()[0]
    assert start_time == 0
    assert end_time == 24


def test_plot_creates_one_graph_per_selected_label():
    _app()
    window = PlotTTYMainWindow()

    values = window.engine.extract("temp=23.4 humidity=51", timestamp=1.0)
    window.plot.append_values(values)

    assert set(window.plot._plots) == {"temp", "humidity"}

    window.plot._series_actions["humidity"].setChecked(False)

    assert set(window.plot._plots) == {"temp"}
    assert "humidity" in window.plot._series


def test_plot_does_not_append_hidden_series():
    _app()
    window = PlotTTYMainWindow()

    values = window.engine.extract("temp=23.4 humidity=51", timestamp=1.0)
    window.plot.append_values(values)
    window.plot._series_actions["humidity"].setChecked(False)

    values = window.engine.extract("temp=24.5 humidity=52", timestamp=2.0)
    window.plot.append_values(values)

    assert window.plot._series["temp"].sample_count() == 2
    assert window.plot._series["humidity"].sample_count() == 1


def test_plot_uses_raw_samples_when_visible_points_fit_target_bucket_count():
    _app()
    window = PlotTTYMainWindow()
    window.plot.bucket_count.setValue(100)

    for index in range(50):
        values = window.engine.extract(f"temp={index}", timestamp=float(index))
        window.plot.append_values(values)

    window.plot._toggle_auto_scroll(False)
    displayed_count = len(window.plot._curves["temp"].getData()[0])

    assert displayed_count == 50


def test_plot_bucket_count_can_be_overridden():
    _app()
    window = PlotTTYMainWindow()
    window.plot.bucket_count.setValue(10)

    for index in range(200):
        values = window.engine.extract(f"temp={index}", timestamp=float(index))
        window.plot.append_values(values)

    window.plot._toggle_auto_scroll(False)
    displayed_count = len(window.plot._curves["temp"].getData()[0])

    assert displayed_count <= 40


def test_plot_shows_visible_point_count():
    _app()
    window = PlotTTYMainWindow()

    for index in range(25):
        values = window.engine.extract(f"temp={index}", timestamp=float(index))
        window.plot.append_values(values)

    window.plot._refresh_pending_data()

    assert window.plot.visible_points_label.text() == "Visible points: 11"


def test_plot_shows_target_samples_per_bucket():
    _app()
    window = PlotTTYMainWindow()
    window.plot.bucket_count.setValue(10)

    for index in range(200):
        values = window.engine.extract(f"temp={index}", timestamp=float(index))
        window.plot.append_values(values)

    window.plot._toggle_auto_scroll(False)

    assert window.plot.samples_per_bucket_label.text() == "Samples/bucket: 20"


def test_rules_widget_shows_separated_list_positions_as_one_based():
    _app()
    widget = ExtractionRulesWidget()
    widget.set_rules([ExtractionRule(label="Humidity", mode="delimiter_column", extra_setting="1", delimiter=",")])

    assert widget.table.item(0, 4).text() == ","
    assert widget.table.item(0, 5).text() == "2"
    assert widget.rules()[0].extra_setting == "1"
    assert widget.rules()[0].delimiter == ","


def test_rules_widget_starts_with_one_default_rule():
    _app()
    widget = ExtractionRulesWidget()

    assert widget.table.rowCount() == 1
    assert widget.rules()[0].mode == "auto_key_value"
