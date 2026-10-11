"""Session options plus exactly one backend's connection settings."""
from dataclasses import dataclass, field
from .serial_transport import SerialSettings
from .rtt_transport import RttSettings


@dataclass
class ConnectionSettings:
    transport: SerialSettings | RttSettings = field(default_factory=SerialSettings)
    encoding: str = "utf-8"
    line_ending: str = "\n"
    log_to_file: bool = True
