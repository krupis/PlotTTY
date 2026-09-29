"""Serial connection session controller."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from ..core.extraction import CapturedValue, ExtractionEngine, ExtractionRule
from ..core.line_decoder import LineDecoder
from ..core.serial_log import SerialSessionLog
from ..core.binary_logging import PlotSessionLog
from ..core.serial_transport import SerialSettings, SerialTransport


RECEIVE_RATE_REFRESH_INTERVAL_MS = 100
RECEIVE_RATE_WINDOW_SECONDS = 1.0


class SerialSession(QObject):
    connectedChanged = Signal(bool)
    receivedText = Signal(str)
    sentText = Signal(str)
    valuesCaptured = Signal(list)
    receiveRateChanged = Signal(float)
    consoleText = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = SerialSettings()
        self._connection: SerialTransport | None = None
        self._line_decoder = LineDecoder()
        self._engine = ExtractionEngine()
        self._serial_log = SerialSessionLog()
        self._plot_log = PlotSessionLog()
        self._receive_rate_samples: deque[tuple[float, int]] = deque()

        self._receive_rate_timer = QTimer(self)
        self._receive_rate_timer.setInterval(RECEIVE_RATE_REFRESH_INTERVAL_MS)
        self._receive_rate_timer.timeout.connect(self.update_receive_rate)
        self._receive_rate_timer.start()
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.setInterval(1000)
        self._log_flush_timer.timeout.connect(self.flush_logs)
        self._log_flush_timer.start()

    @property
    def is_connected(self) -> bool:
        return bool(self._connection and self._connection.is_open)

    @property
    def log_dir(self) -> Path:
        return self._serial_log.log_dir

    @property
    def recording_paths(self) -> tuple[Path, ...]:
        """Current/most recent recording paths, for status and tooltips."""
        return tuple(path for path in (self._serial_log.path, self._plot_log.path) if path is not None)

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self._engine = ExtractionEngine(rules)

    def connect_serial(self) -> None:
        if self.is_connected:
            return
        if not self.settings.port:
            raise RuntimeError("Choose a serial port in the top bar first.")

        transport = SerialTransport(self.settings, self)
        message = f"[connected to {self.settings.port} at {self.settings.baudrate} baud]"
        try:
            self._line_decoder = LineDecoder(self.settings.encoding)
            transport.open()
            if self.settings.log_to_file:
                self._serial_log.start(self.settings.port, self.settings.baudrate)
                self._plot_log.start(self.settings.port, self.settings.baudrate)
                self._serial_log.write_status(message)
        except Exception:
            transport.close()
            transport.deleteLater()
            self._close_logs()
            raise

        self._connection = transport
        transport.bytesReceived.connect(self.on_receive)
        transport.errorReceived.connect(self.on_serial_error)
        self.reset_receive_rate()
        self.connectedChanged.emit(True)
        self.consoleText.emit(f"{message}\n")

    def disconnect_serial(self) -> None:
        was_connected = self._close_connection()
        error = None
        try:
            if was_connected and self.settings.log_to_file:
                self._serial_log.write_status("[disconnected]")
            if was_connected:
                self.consoleText.emit("[disconnected]\n")
        except (OSError, ValueError) as exc:
            error = exc
        error = error or self._close_logs()
        if error is not None:
            self.errorOccurred.emit(f"Recording stopped: {error}")

    def _close_connection(self) -> bool:
        was_connected = self.is_connected
        if self._connection:
            self._connection.blockSignals(True)
            self._connection.close()
            self._connection.deleteLater()
            self._connection = None
        self.connectedChanged.emit(False)
        return was_connected

    def send_command(self, command: str) -> None:
        if not self._connection or not self._connection.is_open:
            raise RuntimeError("Connect to a serial port before sending commands")

        self._connection.write_text(command)
        if self.settings.log_to_file:
            try:
                self._serial_log.write_sent(command)
            except (OSError, ValueError) as exc:
                self._handle_log_error(exc)
        self.sentText.emit(f"{command}\n")

    def reset_receive_rate(self) -> None:
        self._receive_rate_samples.clear()
        self.receiveRateChanged.emit(0.0)

    @Slot(bytes, float)
    def on_receive(self, data: bytes, received_at: float | None = None) -> None:
        if not data:
            return
        self._receive_rate_samples.append((monotonic(), len(data)))
        if self.settings.log_to_file:
            try:
                self._serial_log.write_received(data, self._line_decoder.encoding)
            except (OSError, ValueError) as exc:
                self._handle_log_error(exc)
                return
        self.receivedText.emit(data.decode(self._line_decoder.encoding, errors="replace"))
        if self.settings.raw_capture_mode:
            return

        captured_values: list[CapturedValue] = []
        for line in self._line_decoder.feed(data):
            captured_values.extend(self._engine.extract(line, timestamp=received_at))

        if captured_values:
            if self.settings.log_to_file:
                try:
                    self._plot_log.write_values(captured_values)
                except (OSError, ValueError) as exc:
                    self._handle_log_error(exc)
            self.valuesCaptured.emit(captured_values)

    @Slot(str)
    def on_serial_error(self, message: str) -> None:
        if self._connection is not None:
            self.disconnect_serial()
        self.errorOccurred.emit(message)

    @Slot()
    def flush_logs(self) -> None:
        try:
            self._serial_log.flush()
            self._plot_log.flush()
        except (OSError, ValueError) as exc:
            self._handle_log_error(exc)

    def _close_logs(self) -> Exception | None:
        error = None
        for log in (self._serial_log, self._plot_log):
            try:
                log.close()
            except (OSError, ValueError) as exc:
                error = error or exc
        return error

    def _handle_log_error(self, error: Exception) -> None:
        # Preserve the write failure; close failures are secondary diagnostics.
        self._close_connection()
        self._close_logs()
        self.errorOccurred.emit(f"Recording stopped: {error}")

    @Slot()
    def update_receive_rate(self) -> None:
        now = monotonic()
        cutoff = now - RECEIVE_RATE_WINDOW_SECONDS
        while self._receive_rate_samples and self._receive_rate_samples[0][0] < cutoff:
            self._receive_rate_samples.popleft()

        byte_count = sum(byte_count for _timestamp, byte_count in self._receive_rate_samples)
        bytes_per_second = byte_count / RECEIVE_RATE_WINDOW_SECONDS
        self.receiveRateChanged.emit(bytes_per_second)
