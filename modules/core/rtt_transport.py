"""Native J-Link RTT byte-stream transport."""
from __future__ import annotations
from dataclasses import dataclass
from threading import Event, Lock, Thread, current_thread
from time import time
from .transport import Transport


@dataclass
class RttSettings:
    target: str = ""
    probe_serial: str = ""
    interface: str = "SWD"
    speed_khz: int = 4000
    control_block: str = ""
    up_channel: int = 0
    down_channel: int = 0


class RttTransport(Transport):
    """J-Link RTT transport; reads run on a polling thread."""

    settings: RttSettings

    def __init__(self, settings: RttSettings, *, on_bytes_received, on_error, parent=None):
        super().__init__(settings, on_bytes_received=on_bytes_received, on_error=on_error, parent=parent)
        self._jlink = None
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    @property
    def is_open(self) -> bool:
        return self._jlink is not None

    @property
    def connection_description(self) -> str:
        return f"J-Link RTT {self.settings.target.strip()}, up channel {self.settings.up_channel}"

    def open(self) -> None:
        try:
            import pylink
        except ImportError as exc:
            raise RuntimeError("RTT support requires pylink-square. Install the application requirements.") from exc
        target = self.settings.target.strip()
        if not target:
            raise RuntimeError("Enter the RTT target device name in connection settings.")
        jlink = pylink.JLink()
        try:
            serial = self.settings.probe_serial.strip()
            jlink.open(serial_no=int(serial) if serial else None)
            interface = pylink.enums.JLinkInterfaces.SWD if self.settings.interface == "SWD" else pylink.enums.JLinkInterfaces.JTAG
            jlink.set_tif(interface)
            jlink.connect(target, speed=self.settings.speed_khz)
            address = self.settings.control_block.strip()
            jlink.rtt_start(int(address, 0) if address else None)
        except Exception:
            try:
                jlink.close()
            except Exception:
                pass  # Cleanup must not replace the original connection error.
            raise
        self._jlink = jlink
        self._thread = Thread(target=self._poll, name="PlotTTY-RTT", daemon=True)
        self._thread.start()
        self.opened.emit(self)

    def _poll(self) -> None:
        while not self._stop.is_set():
            try:
                with self._lock:
                    data = self._jlink.rtt_read(self.settings.up_channel, 4096) if self._jlink else []
                if data:
                    self.bytesReceived.emit(self, bytes(data), time())
            except Exception as exc:
                if not self._stop.is_set():
                    self.errorReceived.emit(self, f"J-Link RTT: {exc}")
                return
            self._stop.wait(0.01)

    def write(self, data: bytes) -> None:
        if not self.is_open:
            raise RuntimeError("J-Link RTT is not connected.")
        with self._lock:
            written = self._jlink.rtt_write(self.settings.down_channel, data)
        if written != len(data):
            raise RuntimeError(f"RTT down channel accepted {written} of {len(data)} bytes.")

    def close(self) -> None:
        super().close()
        self._stop.set()
        if self._thread and self._thread is not current_thread():
            self._thread.join(timeout=1.0)
        if self._jlink is not None:
            try:
                with self._lock:
                    try:
                        self._jlink.rtt_stop()
                    finally:
                        self._jlink.close()
            except Exception:
                pass  # A failed probe must not prevent the session from disconnecting.
            finally:
                self._jlink = None

