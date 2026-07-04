"""Shared application data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ExtractionMode = Literal["auto_key_value", "first_number", "regex", "delimiter_column"]


@dataclass(frozen=True)
class CapturedValue:
    timestamp: float
    label: str
    value: float
    unit: str = ""
    raw_text: str = ""


@dataclass
class ExtractionRule:
    label: str
    mode: ExtractionMode = "auto_key_value"
    enabled: bool = True
    sample_counter: bool = False
    extra_setting: str = ""
    delimiter: str = ","
    unit: str = ""
