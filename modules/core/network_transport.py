"""Asynchronous TCP client and UDP endpoint using Qt's nonblocking sockets."""
from dataclasses import dataclass
from time import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QHostInfo, QTcpSocket, QUdpSocket

from .transport import Transport


RECEIVE_BATCH_BYTES = 8192


@dataclass
class TcpSettings:
    host: str = "127.0.0.1"
    port: int = 9000


@dataclass
class UdpSettings:
    bind_address: str = "0.0.0.0"
    local_port: int = 9000
    remote_host: str = ""
    remote_port: int = 9000


class NetworkTransport(Transport):
    """Bound each receive turn so a busy socket cannot monopolize the UI."""

    def __init__(self, settings, *, on_bytes_received, on_error, parent=None):
        super().__init__(settings, on_bytes_received=on_bytes_received, on_error=on_error, parent=parent)
        self._socket = None
        self._ready = False
        self._lookup_id = None
        self._remote_address = None
        self._peer_closed = False
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(8)
        self._timer.timeout.connect(self._receive)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(10000)
        self._deadline.timeout.connect(lambda: self.errorReceived.emit(self, "Network connection timed out."))

    @property
    def is_open(self):
        return self._ready

    def _configure_socket(self, socket):
        self._socket = socket
        socket.errorOccurred.connect(self._on_error)
        self._deadline.start()

    def _on_error(self, _error):
        if self._socket is not None:
            self.errorReceived.emit(self, self._socket.errorString())

    def _mark_ready(self):
        self._deadline.stop()
        self._ready = True
        self._timer.start()
        self.opened.emit(self)

    def close(self):
        super().close()
        self._timer.stop()
        self._deadline.stop()
        self._ready = False
        self._peer_closed = False
        self._remote_address = None
        if self._lookup_id is not None:
            QHostInfo.abortHostLookup(self._lookup_id)
            self._lookup_id = None
        if self._socket is not None:
            self._socket.blockSignals(True)
            self._socket.abort()
            self._socket.deleteLater()
            self._socket = None


class TcpTransport(NetworkTransport):
    def _on_error(self, error):
        if error == QAbstractSocket.SocketError.RemoteHostClosedError:
            # Deliver the peer's final buffered records before disconnecting.
            self._peer_closed = True
            self._receive()
        else:
            super()._on_error(error)

    @property
    def connection_description(self):
        description = f"TCP {self.settings.host}:{self.settings.port}"
        return description

    def open(self):
        if self._socket is not None:
            return
        host = self.settings.host.strip()
        if not host or not 1 <= self.settings.port <= 65535:
            raise ValueError("Enter a TCP host and a port between 1 and 65535.")
        self.blockSignals(False)
        socket = QTcpSocket(self)
        self._configure_socket(socket)
        socket.setReadBufferSize(1024 * 1024)
        socket.connected.connect(self._mark_ready)
        socket.connectToHost(host, self.settings.port)

    def _receive(self):
        if self._socket is not None and self._ready:
            data = bytes(self._socket.read(RECEIVE_BATCH_BYTES))
            if data:
                self.bytesReceived.emit(self, data, time())
            if self._peer_closed and not self._socket.bytesAvailable():
                self.errorReceived.emit(self, "TCP peer closed the connection.")

    def write(self, data):
        if not self.is_open:
            raise RuntimeError("TCP is not connected.")
        # Avoid unbounded buffering when the peer stops reading commands.
        if self._socket.bytesToWrite() + len(data) > 1024 * 1024:
            raise RuntimeError("TCP send buffer is full; wait before sending again.")
        if self._socket.write(data) != len(data):
            raise RuntimeError(self._socket.errorString())


class UdpTransport(NetworkTransport):
    @property
    def connection_description(self):
        description = f"UDP {self.settings.bind_address}:{self.settings.local_port}"
        return description

    def open(self):
        if self._socket is not None:
            return
        address = QHostAddress(self.settings.bind_address.strip())
        if address.isNull() or not 1 <= self.settings.local_port <= 65535:
            raise ValueError("Enter a numeric UDP bind address and a local port between 1 and 65535.")
        if self.settings.remote_host.strip() and not 1 <= self.settings.remote_port <= 65535:
            raise ValueError("Enter a UDP destination port between 1 and 65535.")
        self.blockSignals(False)
        socket = QUdpSocket(self)
        self._configure_socket(socket)
        if not socket.bind(address, self.settings.local_port, QAbstractSocket.BindFlag.DontShareAddress):
            message = socket.errorString()
            self.close()
            raise RuntimeError(message)
        socket.setSocketOption(QAbstractSocket.SocketOption.ReceiveBufferSizeSocketOption, 1024 * 1024)
        remote = self.settings.remote_host.strip()
        if remote:
            self._lookup_id = QHostInfo.lookupHost(remote, self._resolved)
        else:
            self._mark_ready()

    def _resolved(self, info):
        self._lookup_id = None
        if self._socket is None:
            return
        protocol = self._socket.localAddress().protocol()
        addresses = [address for address in info.addresses() if address.protocol() == protocol]
        if info.error() != QHostInfo.HostInfoError.NoError or not addresses:
            reason = info.errorString() if info.error() != QHostInfo.HostInfoError.NoError else "No address matches the bind address IP family."
            self.errorReceived.emit(self, f"Could not resolve UDP destination: {reason}")
            return
        self._remote_address = addresses[0]
        self._mark_ready()

    def _receive(self):
        if self._socket is None or not self._ready:
            return
        chunks = []
        received = 0
        # Datagram boundaries do not supply line delimiters; send newline-terminated records.
        for _ in range(256):
            if not self._socket.hasPendingDatagrams() or received >= RECEIVE_BATCH_BYTES:
                break
            datagram = self._socket.receiveDatagram()
            data = bytes(datagram.data())
            chunks.append(data)
            received += len(data)
        if received:
            payload = b"".join(chunks)
            self.bytesReceived.emit(self, payload, time())

    def write(self, data):
        if not self.is_open:
            raise RuntimeError("UDP is not open.")
        if self._remote_address is None:
            raise RuntimeError("Set a UDP destination host in connection settings before sending commands.")
        if len(data) > 65507:
            raise ValueError("A UDP command must fit in one datagram (at most 65507 bytes).")
        if self._socket.writeDatagram(data, self._remote_address, self.settings.remote_port) != len(data):
            raise RuntimeError(self._socket.errorString())
