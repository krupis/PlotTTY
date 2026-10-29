"""Shared connection session: decoding, extraction, recording, and status."""

from __future__ import annotations

from collections import deque
from enum import Enum
from pathlib import Path
from time import monotonic, time

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from ..core.extraction import CapturedValue, ExtractionEngine, ExtractionRule
from ..core.line_decoder import LineDecoder
from ..core.serial_log import SerialSessionLog
from ..core.binary_logging import PlotSessionLog
from ..core.connection_settings import ConnectionSettings
from ..core.transport import Transport
from ..core.serial_transport import SerialSettings, SerialTransport
from ..core.rtt_transport import RttSettings, RttTransport
from ..core.network_transport import TcpSettings, TcpTransport, UdpSettings, UdpTransport


RECEIVE_RATE_REFRESH_INTERVAL_MS = 100
RECEIVE_RATE_WINDOW_SECONDS = 1.0


TRANSPORT_TYPES = {
    SerialSettings: SerialTransport,
    RttSettings: RttTransport,
    TcpSettings: TcpTransport,
    UdpSettings: UdpTransport,
}


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"


class ConnectionSession(QObject):
    stateChanged = Signal(object)
    receivedText = Signal(str, float)
    sentText = Signal(str)
    valuesCaptured = Signal(list)
    receiveRateChanged = Signal(float)
    consoleText = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = ConnectionSettings()
        self._connection: Transport | None = None
        self._state = ConnectionState.DISCONNECTED
        self._line_decoder = LineDecoder()
        self._extraction_engine = ExtractionEngine()
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
    def state(self) -> ConnectionState:
        return self._state

    def _set_state(self, state: ConnectionState) -> None:
        if state is not self._state:
            self._state = state
            self.stateChanged.emit(state)

    @property
    def is_connected(self) -> bool:
        connected = self._state is ConnectionState.CONNECTED
        return connected

    @property
    def is_connecting(self) -> bool:
        connecting = self._state is ConnectionState.CONNECTING
        return connecting

    @property
    def log_dir(self) -> Path:
        return self._serial_log.log_dir

    @property
    def recording_paths(self) -> tuple[Path, ...]:
        """Current/most recent recording paths, for status and tooltips."""
        return tuple(path for path in (self._serial_log.path, self._plot_log.path) if path is not None)

    def set_rules(self, rules: list[ExtractionRule]) -> None:
        self._extraction_engine = ExtractionEngine(rules)

    def connect_device(self) -> None:
        if self._connection is not None:
            return
        backend = TRANSPORT_TYPES[type(self.settings.transport)]
        transport = backend(
            settings=self.settings.transport,
            on_bytes_received=self.on_receive,
            on_error=self.on_transport_error,
            parent=self,
        )
        transport.opened.connect(self._on_opened)
        self._connection = transport
        try:
            self._line_decoder = LineDecoder(self.settings.encoding)
            self._set_state(ConnectionState.CONNECTING)
            if transport is self._connection:
                transport.open()
        except Exception:
            self._close_connection()
            self._close_logs()
            raise

    @Slot(object)
    def _on_opened(self, transport):
        if transport is not self._connection or not self.is_connecting:
            return
        message = f"[connected to {transport.connection_description}]"
        try:
            if self.settings.log_to_file:
                self._serial_log.start(transport.connection_description)
                self._plot_log.start(transport.connection_description)
                self._serial_log.write_status(message)
        except (OSError, ValueError) as exc:
            self._handle_log_error(exc)
            return
        self.reset_receive_rate()
        self._set_state(ConnectionState.CONNECTED)
        self.consoleText.emit(f"{message}\n")

    def disconnect_device(self) -> None:
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
            self._connection.close()
            self._connection.deleteLater()
            self._connection = None
        self._set_state(ConnectionState.DISCONNECTED)
        return was_connected

    def send_command(self, command: str) -> None:
        if not self.is_connected:
            raise RuntimeError("Connect before sending commands")

        data = f"{command}{self.settings.line_ending}".encode(self.settings.encoding)
        self._connection.write(data)
        if self.settings.log_to_file:
            try:
                self._serial_log.write_sent(command)
            except (OSError, ValueError) as exc:
                self._handle_log_error(exc)
        self.sentText.emit(f"{command}\n")

    def reset_receive_rate(self) -> None:
        self._receive_rate_samples.clear()
        self.receiveRateChanged.emit(0.0)

    @Slot(object, bytes, float)
    def on_receive(self, source: Transport | None, data: bytes, received_at: float | None = None) -> None:
        if source is not self._connection:
            return
        if not data:
            return
        if received_at is None:
            received_at = time()
        self._receive_rate_samples.append((monotonic(), len(data)))
        if self.settings.log_to_file:
            try:
                self._serial_log.write_received(data, self._line_decoder.encoding)
            except (OSError, ValueError) as exc:
                self._handle_log_error(exc)
                return
        # Decode incrementally so characters split across byte chunks stay intact.
        received_text = self._line_decoder.decode(data)
        # Return only complete lines; the decoder stores the unfinished tail in
        # its _partial_line buffer and prepends it to the next chunk's text.
        complete_lines = self._line_decoder.split_lines(received_text)
        # Display decoded text immediately, even before a full line arrives.
        if received_text:
            self.receivedText.emit(received_text, received_at)
        # Extract plot values only from complete lines, using this chunk's receive time.
        captured_values: list[CapturedValue] = []
        for line in complete_lines:
            captured_values.extend(self._extraction_engine.extract(line, timestamp=received_at))

        if captured_values:
            if self.settings.log_to_file:
                try:
                    self._plot_log.write_values(captured_values)
                except (OSError, ValueError) as exc:
                    self._handle_log_error(exc)
            self.valuesCaptured.emit(captured_values)

    @Slot(object, str)
    def on_transport_error(self, source: Transport, message: str) -> None:
        if source is not self._connection:
            return
        self.disconnect_device()
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
