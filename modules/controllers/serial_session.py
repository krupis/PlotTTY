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
        self._receive_rate_timer.timeout.connect(self.update_receive_rate)
        self._receive_rate_timer.start()

    @property
    def is_connected(self) -> bool:
        return bool(self._transport and self._transport.is_open)

    @property
    def log_dir(self) -> Path:
        return self._serial_log.log_dir

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self._engine = ExtractionEngine(rules)

    def connect_serial(self) -> None:
        if self.is_connected:
            return
        if not self.settings.port:
            raise RuntimeError("Use the Settings button and choose a serial port first.")

        transport = SerialTransport(self.settings, self)
        message = f"[connected to {self.settings.port} at {self.settings.baudrate} baud]"
        try:
            self._line_decoder = LineDecoder(self.settings.encoding)
            transport.open()
            if self.settings.log_to_file:
                log_path = self._serial_log.start(self.settings.port, self.settings.baudrate)
                plot_log_path = self._plot_log.start(self.settings.port, self.settings.baudrate)
                self._serial_log.write_status(message)
                status = f"Logging to {log_path} and {plot_log_path}"
            else:
                status = "File logging disabled"
        except Exception:
            transport.close()
            transport.deleteLater()
            self._serial_log.close()
            self._plot_log.close()
            raise

        self._transport = transport
        transport.bytesReceived.connect(self.on_receive)
        transport.errorReceived.connect(self.on_serial_error)
        self.reset_receive_rate()
        self.connectedChanged.emit(True)
        self.statusChanged.emit(status)
        self.statusText.emit(f"{message}\n")

    def disconnect_serial(self) -> None:
        was_connected = self.is_connected
        if self._transport:
            self._transport.blockSignals(True)
            self._transport.close()
            self._transport.deleteLater()
            self._transport = None

        self.connectedChanged.emit(False)
        try:
            if was_connected:
                if self.settings.log_to_file:
                    self._serial_log.write_status("[disconnected]")
                self.statusText.emit("[disconnected]\n")
        finally:
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
    def on_receive(self, data: bytes, received_at: float | None = None) -> None:
        if not data:
            return
        self._receive_rate_samples.append((monotonic(), len(data)))
        if self.settings.log_to_file:
            self._serial_log.write_received(data, self._line_decoder.encoding)
        self.receivedText.emit(data.decode(self._line_decoder.encoding, errors="replace"))
        if self.settings.raw_capture_mode:
            return

        captured_values: list[CapturedValue] = []
        for line in self._line_decoder.feed(data):
            captured_values.extend(self._engine.extract(line, timestamp=received_at))

        if captured_values:
            if self.settings.log_to_file:
                self._plot_log.write_values(captured_values)
            self.valuesCaptured.emit(captured_values)

    @Slot(str)
    def on_serial_error(self, message: str) -> None:
        if self._transport is not None:
            self.disconnect_serial()
        self.errorOccurred.emit(message)

    @Slot()
    def update_receive_rate(self) -> None:
        now = monotonic()
        cutoff = now - RECEIVE_RATE_WINDOW_SECONDS
        while self._receive_rate_samples and self._receive_rate_samples[0][0] < cutoff:
            self._receive_rate_samples.popleft()

        byte_count = sum(byte_count for _timestamp, byte_count in self._receive_rate_samples)
        bytes_per_second = byte_count / RECEIVE_RATE_WINDOW_SECONDS
        self.receiveRateChanged.emit(bytes_per_second)
