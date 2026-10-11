"""Measure raw USB or complete PlotTTY capture without sending commands."""
import argparse
from collections import defaultdict
from functools import wraps
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'benchmarks')]
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtSerialPort import QSerialPort
from PySide6.QtWidgets import QApplication
from mainwindow import MainWindow, apply_application_style
from modules.controllers.connection_session import ConnectionSession
from modules.core.extraction import ExtractionRule
from modules.core.line_decoder import LineDecoder
from modules.widgets.console_widget import ConsoleWidget
from modules.widgets.plot_widget import PlotWidget
from plot_benchmark import stats
from ui_latency import EventLoopLatencyMonitor

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode', choices=('raw', 'live'), default='live')
parser.add_argument('--port', default='COM15')
parser.add_argument('--duration', type=float, default=30)
parser.add_argument('--warmup', type=float, default=3)
parser.add_argument('--console-interactions', action='store_true',
                    help='Search, scroll and copy retained console text during capture.')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.duration <= 0 or args.warmup < 0:
    parser.error('Duration must be positive and warmup nonnegative.')
args.output.mkdir(parents=True, exist_ok=True)
app = QApplication([])
apply_application_style(app)
active = False
started = 0
counts = dict(bytes=0, records=0, gaps=0, discontinuities=0)
payload_sizes = []
displayed_rates = []
timings = defaultdict(list)
errors = []
decoder = LineDecoder()
previous = None
overflow_first = overflow_last = None
device_intervals = []
previous_time = None
gap_details = []
invalid_records = []

def inspect(data):
    global previous, previous_time, overflow_first, overflow_last
    if not active:
        return
    counts['bytes'] += len(data)
    for line in decoder.feed(data):
        fields = line.split(',')
        if len(fields) != 8:
            if len(invalid_records) < 20:
                invalid_records.append(line)
            continue
        try:
            sequence, sample_type = int(fields[0]), int(fields[1])
            timestamp, overflow = float(fields[6]), int(fields[7])
        except ValueError:
            if len(invalid_records) < 20:
                invalid_records.append(line)
            continue
        if sample_type not in range(1, 8):
            continue
        counts['records'] += 1
        payload_sizes.append(len(line.encode('utf-8')) + 2)  # Firmware uses CRLF.
        if previous is not None:
            gap = (sequence - previous - 1) & 0xFFFFFFFF
            if gap < 0x80000000:
                counts['gaps'] += gap
                if gap and len(gap_details) < 20:
                    gap_details.append(dict(previous=previous, sequence=sequence,
                        missing=gap, device_time=timestamp, overflow=overflow,
                        elapsed_seconds=perf_counter() - started))
            else:
                counts['discontinuities'] += 1
        previous = sequence
        if previous_time is not None:
            device_intervals.append((timestamp - previous_time) * 1000000)
        previous_time = timestamp
        if overflow_first is None:
            overflow_first = overflow
        overflow_last = overflow

def instrument(cls, method):
    original = getattr(cls, method)
    @wraps(original)
    def timed(self, *a, **kw):
        if not active:
            return original(self, *a, **kw)
        if method == 'on_receive':
            inspect(a[1])
        tick = perf_counter()
        try:
            return original(self, *a, **kw)
        finally:
            timings[method].append((perf_counter() - tick) * 1000)
    setattr(cls, method, timed)

for cls, method in ((ConnectionSession, 'on_receive'), (ConsoleWidget, 'flush'),
                    (PlotWidget, 'append_values'), (PlotWidget, '_update_visible_curve_data')):
    instrument(cls, method)

window = port = None
interactions = []
console_interactions = defaultdict(list)
console_search_started = None
if args.mode == 'raw':
    port = QSerialPort()
    port.setPortName(args.port)
    port.setBaudRate(115200)
    port.readyRead.connect(lambda: inspect(bytes(port.readAll())))
    if not port.open(QSerialPort.OpenModeFlag.ReadOnly):
        raise SystemExit(port.errorString())
else:
    settings = QSettings(str(args.output / 'layout.ini'), QSettings.Format.IniFormat)
    settings.setValue('Console', True)
    with patch('mainwindow.QSettings', return_value=settings):
        window = MainWindow()
    window.resize(1280, 720)
    rules = [ExtractionRule('Device time', 'delimited_values', is_time=True, extra_setting='6')]
    rules += [ExtractionRule(f'Value {i}', 'delimited_values', extra_setting=str(i)) for i in range(1, 6)]
    window.apply_rules(rules)
    window.session.settings.transport.port = args.port
    window.session._serial_log.log_dir = args.output
    window.session._plot_log.log_dir = args.output
    window.session.errorOccurred.connect(errors.append)
    window.session.receiveRateChanged.connect(lambda rate: displayed_rates.append(rate) if active else None)
    MainWindow.on_transport_error = lambda self, message: errors.append(message)
    window.show()
    app.processEvents()
    window.ui.actionConsole.setChecked(True)
    window.ui.WorkspaceSplitter.set_panel_expanded(True)
    window.plot.on_toggle_fit_capture(True)
    window.session.connect_device()
    def navigate():
        if not window.plot._series:
            return
        for label in window.plot._series:
            window.plot.set_series_style(label, 'dots')
        tick = perf_counter()
        low, high = window.plot._last_time_range
        span = max(.001, (high - low) * .8)
        window.plot._set_time_range(low + span * .1, low + span)
        window.plot.graph.repaint()
        if active:
            interactions.append((perf_counter() - tick) * 1000)
    navigation = QTimer()
    navigation.setInterval(500)
    navigation.timeout.connect(navigate)
    navigation.start()
    if args.console_interactions:
        def search_finished(*_):
            if active and console_search_started is not None:
                console_interactions['search_complete'].append((perf_counter() - console_search_started) * 1000)
        if hasattr(window.console, 'searchFinished'):
            window.console.searchFinished.connect(search_finished)
        def use_console():
            global console_search_started
            if not active:
                return
            tick = perf_counter()
            console_search_started = tick
            result = window.console.find_text('3.30')
            console_interactions['search_dispatch'].append((perf_counter() - tick) * 1000)
            if result is not None:
                search_finished()
            tick = perf_counter()
            bar = getattr(window.console, 'scroll_bar', window.ui.ConsoleTextEdit.verticalScrollBar())
            bar.setValue(bar.maximum() // 2)
            bar.setValue(bar.maximum())
            console_interactions['scroll'].append((perf_counter() - tick) * 1000)
            tick = perf_counter()
            window.ui.ConsoleTextEdit.setFocus()
            window.ui.ConsoleTextEdit.selectAll()
            window.ui.ConsoleTextEdit.copy()
            console_interactions['copy'].append((perf_counter() - tick) * 1000)
        console_timer = QTimer()
        console_timer.setInterval(2000)
        console_timer.timeout.connect(use_console)
        console_timer.start()

monitor = EventLoopLatencyMonitor()
monitor.start()

def finish():
    global active
    elapsed = perf_counter() - started
    active = False
    result = dict(mode=args.mode, elapsed_seconds=elapsed, counts=dict(counts), errors=errors,
                  bytes_per_second=counts['bytes'] / elapsed, records_per_second=counts['records'] / elapsed,
                  latency=monitor.summary(), qt_platform=app.platformName(),
                  stages={name: stats(values) for name, values in timings.items() if values},
                  pan_zoom=stats(interactions) if interactions else None)
    result['console_interactions'] = {name: stats(values) for name, values in console_interactions.items() if values}
    result['gap_details'] = gap_details
    result['invalid_records'] = invalid_records
    result['conditions'] = dict(port=args.port, warmup_seconds=args.warmup,
        requested_duration_seconds=args.duration, console_interactions=args.console_interactions,
        window_size=[window.width(), window.height()] if window else None,
        plot_history_reset_after_warmup=bool(window),
        logging=bool(window and window.session.settings.log_to_file))
    if payload_sizes:
        result['csv_payload'] = dict(mean_record_bytes=sum(payload_sizes) / len(payload_sizes),
            minimum_record_bytes=min(payload_sizes), maximum_record_bytes=max(payload_sizes),
            expected_bytes_per_second_at_10khz=10000 * sum(payload_sizes) / len(payload_sizes))
    if displayed_rates:
        rates = sorted(displayed_rates)
        result['displayed_receive_rate'] = dict(median_bytes_per_second=rates[len(rates) // 2],
            minimum_bytes_per_second=rates[0], maximum_bytes_per_second=rates[-1],
            final_label=window._rate_label.text())
    if device_intervals:
        ordered = sorted(device_intervals)
        result['device_intervals_us'] = dict(median=ordered[len(ordered)//2],
            p95=ordered[int((len(ordered)-1)*.95)], minimum=ordered[0], maximum=ordered[-1])
        result['device_overflows_during_capture'] = (overflow_last - overflow_first) & 0xFFFFFFFF
    if window:
        history = window.console._history
        if hasattr(history, 'size'):
            result['console_history'] = dict(rows=history.count, bytes=history.size,
                                            line_index_bytes=len(history.offsets) * history.offsets.itemsize)
        result['console_visible'] = window.ui.ConsoleTextEdit.isVisible()
        result['plotted_points_per_series'] = {label: len(curve.xData) for label, curve in window.plot._curves.items()}
        result['samples_per_series'] = {label: s.sample_count() for label, s in window.plot._series.items()}
        window.grab().save(str(args.output / 'window.png'))
        window.close()
    if port:
        port.close()
    (args.output / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    app.quit()

def begin():
    global active, started, previous, previous_time, overflow_first, overflow_last, decoder
    decoder = LineDecoder()
    previous = previous_time = overflow_first = overflow_last = None
    counts.update(bytes=0, records=0, gaps=0, discontinuities=0)
    timings.clear()
    interactions.clear()
    monitor._latencies_ms.clear()
    if window:
        window.ui.WorkspaceSplitter.set_panel_expanded(True)
        # The device queues old records while COM15 is closed. Warmup drains
        # those records; exclude their idle-time gap from navigation timings.
        window.plot.clear_values()
        window.plot.on_toggle_fit_capture(True)
    started = perf_counter()
    active = True
    QTimer.singleShot(round(args.duration * 1000), finish)

QTimer.singleShot(round(args.warmup * 1000), begin)
app.exec()
