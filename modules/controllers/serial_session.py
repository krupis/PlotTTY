"""Serial connection session controller."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from time import monotonic

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from ..core.extraction import ExtractionEngine
from ..core.line_decoder import LineDecoder
from ..core.models import CapturedValue, ExtractionRule
from ..core.serial_log import PlotSessionLog, SerialSessionLog
from ..core.serial_transport import SerialSettings, SerialTransport


RECEIVE_RATE_REFRESH_INTERVAL_MS = 100
RECEIVE_RATE_WINDOW_SECONDS = 1.0


class SerialSession(QObject):
    connectedChanged = Signal(bool)
    receivedText = Signal(str)
    sentText = Signal(str)
    valuesCaptured = Signal(list)
    receiveRateChanged = Signal(float)
    statusChanged = Signal(str)
    statusText = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = SerialSettings()
        self._transport: SerialTransport | None = None
        self._line_decoder = LineDecoder()
        self._engine = ExtractionEngine()
        self._serial_log = SerialSessionLog()
        self._plot_log = PlotSessionLog()
        self._receive_rate_samples: deque[tuple[float, int]] = deque()

        self._receive_rate_timer = QTimer(self)
        self._receive_rate_timer.setInterval(RECEIVE_RATE_REFRESH_INTERVAL_MS)
        self._receive_rate_timer.timeout.connect(self.on_refresh_receive_rate)
        self._receive_rate_timer.start()

    @property
    def is_connected(self) -> bool:
        return bool(self._transport and self._transport.is_open)

    @property
    def log_dir(self) -> Path:
        return self._serial_log.log_dir

    def set_settings(self, settings: SerialSettings) -> None:
        self.settings = settings

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self._engine = ExtractionEngine(rules)

    def connect_serial(self) -> None:
        if not self.settings.port:
            raise RuntimeError("Use the Settings button and choose a serial port first.")

        try:
            self._transport = SerialTransport(self.settings, self)
            self._line_decoder = LineDecoder(self.settings.encoding)
            self._transport.bytesReceived.connect(self.on_received_data)
            self._transport.errorReceived.connect(self.on_serial_error)
            self._transport.open()
        except Exception:
            self._transport = None
            raise

        self.reset_receive_rate()
        self.connectedChanged.emit(True)
        message = f"[connected to {self.settings.port} at {self.settings.baudrate} baud]"
        if self.settings.log_to_file:
            log_path = self._serial_log.start(self.settings.port, self.settings.baudrate)
            plot_log_path = self._plot_log.start(self.settings.port, self.settings.baudrate)
            self._serial_log.write_status(message)
            self.statusChanged.emit(f"Logging to {log_path} and {plot_log_path}")
        else:
            self._serial_log.close()
            self._plot_log.close()
            self.statusChanged.emit("File logging disabled")
        self.statusText.emit(f"{message}\n")

    def disconnect_serial(self) -> None:
        was_connected = self.is_connected
        if self._transport:
            self._transport.close()
            self._transport = None

        self.connectedChanged.emit(False)
        if was_connected:
            if self.settings.log_to_file:
                self._serial_log.write_status("[disconnected]")
            self.statusText.emit("[disconnected]\n")
            self._serial_log.close()
            self._plot_log.close()

    def send_command(self, command: str) -> None:
        if not self._transport or not self._transport.is_open:
            raise RuntimeError("Connect to a serial port before sending commands")

        self._transport.write_text(command)
        if self.settings.log_to_file:
            self._serial_log.write_sent(command)
        self.sentText.emit(f"{command}\n")

    def reset_receive_rate(self) -> None:
        self._receive_rate_samples.clear()
        self.receiveRateChanged.emit(0.0)

    @Slot(bytes, float)
    def on_received_data(self, data: bytes, received_at: float | None = None) -> None:
        self._record_received_bytes(len(data))
        if self.settings.log_to_file:
            self._serial_log.write_received(data, self._line_decoder.encoding)
        if self.settings.raw_capture_mode:
            return

        self.receivedText.emit(data.decode(self._line_decoder.encoding, errors="replace"))
        for line in self._line_decoder.feed(data):
            captured_values = self._engine.extract(line, timestamp=received_at)
            if captured_values:
                if self.settings.log_to_file:
                    self._plot_log.write_values(captured_values)
                self.valuesCaptured.emit(captured_values)

    @Slot(str)
    def on_serial_error(self, message: str) -> None:
        if self.is_connected:
            self.disconnect_serial()
        self.errorOccurred.emit(message)

    @Slot()
    def on_refresh_receive_rate(self) -> None:
        now = monotonic()
        cutoff = now - RECEIVE_RATE_WINDOW_SECONDS
        while self._receive_rate_samples and self._receive_rate_samples[0][0] < cutoff:
            self._receive_rate_samples.popleft()

        if not self._receive_rate_samples:
            bytes_per_second = 0.0
        else:
            byte_count = sum(byte_count for _timestamp, byte_count in self._receive_rate_samples)
            bytes_per_second = byte_count / RECEIVE_RATE_WINDOW_SECONDS

        self.receiveRateChanged.emit(bytes_per_second)

    def _record_received_bytes(self, byte_count: int) -> None:
        if byte_count <= 0:
            return

        self._receive_rate_samples.append((monotonic(), byte_count))
