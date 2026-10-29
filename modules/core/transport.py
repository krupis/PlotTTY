"""Shared Qt signals and byte-stream interface for connection backends."""
from PySide6.QtCore import QObject, Qt, Signal


class Transport(QObject):
    """Handlers are connected at construction; events carry their source backend."""
    is_open: bool
    connection_description: str

    bytesReceived = Signal(object, bytes, float)
    errorReceived = Signal(object, str)
    opened = Signal(object)

    def __init__(self, settings, *, on_bytes_received, on_error, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.bytesReceived.connect(on_bytes_received, Qt.ConnectionType.QueuedConnection)
        self.errorReceived.connect(on_error, Qt.ConnectionType.QueuedConnection)

    def open(self) -> None:
        """Begin opening; emit opened(self) when ready, immediately or later."""
        raise NotImplementedError

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def close(self) -> None:
        self.blockSignals(True)
