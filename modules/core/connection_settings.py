"""Session options plus exactly one backend's connection settings."""
from dataclasses import dataclass, field
from .serial_transport import SerialSettings
from .rtt_transport import RttSettings
from .network_transport import TcpSettings, UdpSettings


@dataclass
class ConnectionSettings:
    transport: SerialSettings | RttSettings | TcpSettings | UdpSettings = field(default_factory=SerialSettings)
    encoding: str = "utf-8"
    line_ending: str = "\n"
    log_to_file: bool = False
