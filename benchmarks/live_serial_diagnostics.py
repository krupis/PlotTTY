"""Run the real PlotTTY window against a serial device with scoped timings.

Uses six comma-delimited Y rules (fields 0..5), 115200 8N1, logging on.
No commands are transmitted to the device. JSON/logs are written to --output.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
import json
import hashlib
from pathlib import Path
import sys
from time import perf_counter
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM15')
    parser.add_argument('--duration', type=float, default=25)
    parser.add_argument('--warmup', type=float, default=10)
    parser.add_argument('--renderer', choices=['gl', 'raster'], default='gl')
    parser.add_argument('--no-console', action='store_true')
    parser.add_argument('--no-plot', action='store_true')
    parser.add_argument('--no-logging', action='store_true')
    parser.add_argument('--frame-ms', type=int)
    parser.add_argument('--no-vsync', action='store_true')
    parser.add_argument('--detail', action='store_true')
    parser.add_argument('--prepare-view', action='store_true')
    parser.add_argument('--precise', action='store_true')
    parser.add_argument('--profile', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-snapshot', type=Path,
                        help='Load plotter.py and plot_widget.py from a saved baseline directory')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    if args.source_snapshot:
        import importlib.util
        # A separate worker can replay the original implementation without
        # replacing or editing the user's current production source files.
        for name in ('modules.core.plotter', 'modules.widgets.plot_widget'):
            path = args.source_snapshot / (name.rsplit('.', 1)[-1] + '.py')
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)

    import numpy as np
    from PySide6.QtCore import QEvent, QTimer
    from PySide6.QtWidgets import QApplication
    from modules.controllers.serial_session import SerialSession
    from modules.core.extraction import ExtractionEngine
    from modules.core.line_decoder import LineDecoder
    from modules.core.plotter import Plotter
    from modules.core.serial_log import SerialSessionLog, PlotSessionLog
    from modules.core.serial_transport import SerialSettings
    from modules.core.models import ExtractionRule
    from modules.core.ui_latency import EventLoopLatencyMonitor
    from modules.widgets.console_widget import ConsoleWidget
    from modules.widgets.plot_widget import PlotWidget

    enabled = False
    timings = defaultdict(list)
    exclusive = defaultdict(float)
    stack = []
    counts = defaultdict(int)
    errors = []
    sequence = {'first': None, 'last': None, 'gaps': 0, 'backwards': 0}
    latencies = []
    timeline = []

    @contextmanager
    def stage(name):
        if not enabled:
            yield
            return
        entry = [perf_counter(), 0.0]
        stack.append(entry)
        try:
            yield
        finally:
            elapsed = perf_counter() - entry[0]
            stack.pop()
            timings[name].append(elapsed * 1000)
            exclusive[name] += elapsed - entry[1]
            if stack:
                stack[-1][1] += elapsed

    def instrument(cls, method, name):
        original = getattr(cls, method)
        @wraps(original)
        def wrapped(self, *a, **kw):
            with stage(name):
                return original(self, *a, **kw)
        setattr(cls, method, wrapped)

    original_receive = SerialSession.on_receive
    def receive(self, data, received_at=None):
        if enabled:
            counts['bytes'] += len(data)
            counts['chunks'] += 1
            counts['max_chunk_bytes'] = max(counts['max_chunk_bytes'], len(data))
        with stage('receive_total'):
            return original_receive(self, data, received_at)
    SerialSession.on_receive = receive

    original_extract = ExtractionEngine.extract
    def extract(self, *a, **kw):
        with stage('extract'):
            values = original_extract(self, *a, **kw)
        if enabled:
            counts['lines'] += 1
            counts['values'] += len(values)
            if len(values) != 6:
                counts['lines_without_six_values'] += 1
            if values and values[0].label == 'Value 0':
                counter = int(values[0].value)
                if sequence['first'] is None:
                    sequence['first'] = counter
                if sequence['last'] is not None:
                    delta = counter - sequence['last']
                    if delta > 1:
                        sequence['gaps'] += delta - 1
                    elif delta <= 0:
                        sequence['backwards'] += 1
                sequence['last'] = counter
        return values
    ExtractionEngine.extract = extract

    for cls, method, name in [
        (LineDecoder, 'feed', 'decode_lines'),
        (SerialSessionLog, 'write_received', 'console_log'),
        (PlotSessionLog, 'write_values', 'csv_log'),
        (PlotWidget, 'append_values', 'append_store'),
        (PlotWidget, '_update_visible_curve_data', 'curve_update'),
        (PlotWidget, '_set_time_range', 'range_update'),
        (Plotter, 'read_visible_samples', 'read_downsample'),
        (ConsoleWidget, 'flush', 'console_flush'),
    ]:
        instrument(cls, method, name)
    if args.detail:
        from pyqtgraph import AxisItem, PlotCurveItem, ViewBox
        instrument(AxisItem, 'generateDrawSpecs', 'axis_layout')
        instrument(AxisItem, 'paint', 'axis_paint')
        instrument(PlotCurveItem, 'paint', 'curve_paint')
        instrument(ViewBox, 'updateAutoRange', 'auto_range')
    if args.prepare_view:
        update_curves = PlotWidget._update_visible_curve_data
        def prepare_update(self, *a, **kw):
            result = update_curves(self, *a, **kw)
            with stage('prepare_scene'):
                self.graph.scene().prepareForPaint()
            return result
        PlotWidget._update_visible_curve_data = prepare_update
    original_tick = EventLoopLatencyMonitor.on_tick
    def tick(self):
        original_tick(self)
        if enabled and self._latencies_ms:
            latencies.append(self._latencies_ms[-1])
    EventLoopLatencyMonitor.on_tick = tick

    class App(QApplication):
        def notify(self, receiver, event):
            if event.type() == QEvent.Type.Paint:
                with stage('paint'):
                    return super().notify(receiver, event)
            return super().notify(receiver, event)

    def error_hook(kind, value, tb):
        errors.append(''.join(traceback.format_exception(kind, value, tb)))
        sys.__excepthook__(kind, value, tb)
    sys.excepthook = error_hook
    if args.no_vsync:
        from PySide6.QtGui import QSurfaceFormat
        fmt = QSurfaceFormat.defaultFormat()
        fmt.setSwapInterval(0)
        QSurfaceFormat.setDefaultFormat(fmt)
    app = App([])
    from mainwindow import MainWindow, apply_application_style
    apply_application_style(app)
    # Avoid a blocking message box if a device error occurs during automation.
    MainWindow.on_serial_error = lambda self, message: errors.append(message)
    window = MainWindow()
    window.resize(1880, 1000)
    window.setWindowTitle('PlotTTY live diagnostics — ' + args.output.name)
    window.rules_table.set_rules([
        ExtractionRule(label=f'Value {i}', mode='delimiter_column', extra_setting=str(i), delimiter=',')
        for i in range(6)
    ])
    window.session.settings = SerialSettings(port=args.port, log_to_file=not args.no_logging)
    window.session._serial_log.log_dir = args.output
    window.session._plot_log.log_dir = args.output
    window.plot.opengl_button.setChecked(args.renderer == 'gl')
    window.plot.on_toggle_show_all(True)
    if args.frame_ms:
        window.plot._timer.setInterval(args.frame_ms)
    if args.precise:
        from PySide6.QtCore import Qt
        window.plot._timer.setTimerType(Qt.TimerType.PreciseTimer)
    if args.no_console:
        window.session.receivedText.disconnect(window.console.append_received)
    if args.no_plot:
        window.plot._timer.stop()
    window.show()
    window.raise_()
    window.activateWindow()
    app.processEvents()
    try:
        window.session.connect_serial()
    except Exception as exc:
        (args.output / 'connection_error.txt').write_text(str(exc), encoding='utf-8')
        window.close()
        raise
    profiler = None
    if args.profile:
        import cProfile
        profiler = cProfile.Profile()
    started = None

    def begin():
        nonlocal enabled, started
        window._latency_monitor._latencies_ms.clear()
        started = perf_counter()
        enabled = True
        if profiler:
            profiler.enable()
        print('MEASURING', args.output.name, flush=True)
        QTimer.singleShot(round(args.duration * 1000), finish)

    def summarize(values):
        if not values:
            return {'count': 0}
        return {'count': len(values), 'median_ms': float(np.median(values)),
                'p95_ms': float(np.percentile(values, 95)),
                'p99_ms': float(np.percentile(values, 99)), 'max_ms': float(max(values))}

    def snapshot():
        if enabled:
            timeline.append({'seconds': perf_counter()-started,
                             'visible': window.isVisible(), 'minimized': window.isMinimized(),
                             'exposed': window.windowHandle().isExposed(),
                             'latency': window._latency_monitor.summary(),
                             'bytes': counts['bytes'], 'lines': counts['lines']})

    def finish():
        nonlocal enabled
        if profiler:
            profiler.disable()
            profiler.dump_stats(str(args.output / 'profile.pstats'))
        enabled = False
        elapsed = perf_counter()-started
        window.session.disconnect_serial()
        window.grab().save(str(args.output / 'window.png'))
        result = {'settings': {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()},
                  'elapsed_seconds': elapsed, 'counts': dict(counts), 'sequence': sequence,
                  'window_visible': window.isVisible(), 'window_minimized': window.isMinimized(),
                  'window_exposed': window.windowHandle().isExposed(),
                  'refresh_interval_ms': window.plot._timer.interval(),
                  'bytes_per_second': counts['bytes']/elapsed, 'lines_per_second': counts['lines']/elapsed,
                  'latency': summarize(latencies), 'stages': {}, 'errors': errors, 'timeline': timeline,
                  'samples_per_series': {k:v.sample_count() for k,v in window.plot._series.items()},
                  'plotted_points': {k:len(v.xData) for k,v in window.plot._curves.items() if v.xData is not None}}
        for name, values in timings.items():
            result['stages'][name] = {**summarize(values), 'total_ms': sum(values),
                                     'exclusive_ms': exclusive[name]*1000,
                                     'exclusive_wall_percent': exclusive[name]/elapsed*100}
        result['valid_for_comparison'] = (
            not errors and counts['lines'] > 0 and
            all(t['exposed'] and not t['minimized'] for t in timeline) and
            (args.no_plot or len(timings['paint']) > 0)
        )
        result['source_sha256'] = {}
        for path in ['modules/core/plotter.py', 'modules/core/buckets.py',
                     'modules/widgets/plot_widget.py', 'modules/widgets/console_widget.py']:
            source = ROOT / path
            if args.source_snapshot and source.name in ('plotter.py', 'plot_widget.py'):
                source = args.source_snapshot / source.name
            result['source_sha256'][path] = hashlib.sha256(source.read_bytes()).hexdigest()
        (args.output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'latency': result['latency'], 'lines_per_second': result['lines_per_second'],
                          'sequence': sequence, 'stages': result['stages'], 'errors':errors}), flush=True)
        window.close()
        app.quit()

    reporter = QTimer()
    reporter.timeout.connect(snapshot)
    reporter.start(1000)
    QTimer.singleShot(round(args.warmup*1000), begin)
    app.exec()
    if errors:
        raise RuntimeError(errors)


if __name__ == '__main__':
    main()
