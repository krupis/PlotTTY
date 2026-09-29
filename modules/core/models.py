"""Shared application data models."""

from __future__ import annotations

from dataclasses import dataclass
import re
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


RULE_MODES = {
    "auto_key_value": ("Named values", "Extract all name/value pairs, such as Voltage: 3.31."),
    "delimiter_column": ("Delimited values", "Extract a number from one zero-based field index."),
    "regex": ("Regex pattern", "The first capture group must contain the numeric value."),
    "first_number": ("First number", "Extract the first number found in each line."),
}


def validate_rules(rules: list[ExtractionRule]) -> None:
    """Reject invalid drafts/profiles with row-specific messages."""
    errors = []
    for row, rule in enumerate(rules, 1):
        try:
            if rule.mode not in RULE_MODES:
                raise ValueError(f"Unknown extraction mode: {rule.mode}")
            if rule.mode == "regex" and re.compile(rule.extra_setting).groups < 1:
                raise ValueError("Regex must contain a capture group for the numeric value.")
            if rule.mode == "delimiter_column":
                if not rule.extra_setting.isdecimal():
                    raise ValueError("Field index must be a nonnegative integer.")
                if not rule.delimiter:
                    raise ValueError("Delimiter must not be empty.")
        except (ValueError, TypeError, AttributeError, re.error) as exc:
            errors.append(f"Row {row}: {exc}")
    if errors:
        raise ValueError("\n".join(errors))
