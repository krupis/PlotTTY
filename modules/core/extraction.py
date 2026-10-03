"""Extract numeric values from serial text."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from time import time
from typing import Literal


NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
NAMED_VALUES_RE = re.compile(
    rf"([A-Za-z_][\w .\-/]*)\s*(?:=|:)\s*({NUMBER_PATTERN})\s*"
    rf"((?![A-Za-z_][\w.\-/]*\s*(?:=|:))[^\s,;=:]*)?"
)
FIRST_NUMBER_RE = re.compile(NUMBER_PATTERN)

ExtractionMethod = Literal["named_values", "first_number", "regex_pattern", "delimited_values"]


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
    method: ExtractionMethod = "named_values"
    is_time: bool = False
    extra_setting: str = ""
    delimiter: str = ","
    unit: str = ""
    color: str = ""


def validate_rules(rules: Iterable[ExtractionRule]) -> None:
    """Reject rules that the extraction engine cannot execute."""
    errors = []
    for row, rule in enumerate(rules, 1):
        try:
            if not isinstance(rule.color, str) or (rule.color and not re.fullmatch(r"#[0-9a-fA-F]{6}", rule.color)):
                raise ValueError("Color must be a #RRGGBB value or empty for automatic colors.")
            if rule.method not in ("named_values", "first_number", "regex_pattern", "delimited_values"):
                raise ValueError(f"Unknown extraction method: {rule.method}")
            if rule.method == "regex_pattern":
                if not rule.extra_setting:
                    raise ValueError("Regex pattern is required.")
                if re.compile(rule.extra_setting).groups < 1:
                    raise ValueError("Regex must contain a capture group for the numeric value.")
            if rule.method == "delimited_values":
                if not rule.extra_setting.isdecimal():
                    raise ValueError("Field index must be a nonnegative integer.")
                if not rule.delimiter:
                    raise ValueError("Delimiter must not be empty.")
        except (TypeError, ValueError, re.error) as exc:
            errors.append(f"Row {row}: {exc}")
    if errors:
        raise ValueError("\n".join(errors))


class ExtractionEngine:
    """Apply extraction rules to one text line."""

    def __init__(self, rules: Iterable[ExtractionRule] | None = None):
        self.rules = default_rules() if rules is None else list(rules)

    def extract(self, text: str, timestamp: float | None = None) -> list[CapturedValue]:
        timestamp = timestamp if timestamp is not None else time()
        # Split once per delimiter, shared by Time and Plot rules for this line.
        fields: dict[str, list[str]] = {}
        rule_timestamp = _rule_timestamp(self.rules, text, fields)
        timestamp = rule_timestamp if rule_timestamp is not None else timestamp
        captured_values = []

        for rule in self.rules:
            if rule.is_time:
                continue

            captured_values.extend(_extract_rule(rule, text, timestamp, fields))

        return captured_values


def default_rules() -> list[ExtractionRule]:
    return [ExtractionRule(label="Named values", method="named_values")]


def _extract_rule(
    rule: ExtractionRule, text: str, timestamp: float, fields: dict[str, list[str]]
) -> list[CapturedValue]:
    captured_values = []

    if rule.method == "named_values":
        for match in NAMED_VALUES_RE.finditer(text):
            label = match.group(1)
            value = float(match.group(2))
            unit = (match.group(3) or rule.unit or "").strip()
            captured_values.append(_captured_value(timestamp, label, value, unit, text))

    elif rule.method == "first_number":
        match = FIRST_NUMBER_RE.search(text)
        if match:
            value = float(match.group(0))
            captured_values.append(_captured_value(timestamp, rule.label, value, rule.unit, text))

    elif rule.method == "regex_pattern" and rule.extra_setting:
        for match in re.finditer(rule.extra_setting, text):
            if match.groups():
                captured_values.append(
                    _captured_value(timestamp, rule.label, float(match.group(1)), rule.unit, text)
                )

    elif rule.method == "delimited_values":
        try:
            column = int(rule.extra_setting)
        except ValueError:
            return captured_values

        delimiter = rule.delimiter.replace(r"\t", "\t")
        if not delimiter:
            return captured_values

        if delimiter not in fields:
            fields[delimiter] = text.split(delimiter)
        parts = fields[delimiter]
        if 0 <= column < len(parts):
            match = FIRST_NUMBER_RE.search(parts[column])
            if match:
                captured_values.append(
                    _captured_value(timestamp, rule.label, float(match.group(0)), rule.unit, text)
                )

    return captured_values


def _rule_timestamp(
    rules: Iterable[ExtractionRule], text: str, fields: dict[str, list[str]]
) -> float | None:
    for rule in rules:
        if not rule.is_time:
            continue

        values = _extract_rule(rule, text, 0.0, fields)
        if values:
            return values[0].value

    return None


def _captured_value(timestamp: float, label: str, value: float, unit: str, raw_text: str) -> CapturedValue:
    return CapturedValue(
        timestamp=timestamp,
        label=clean_label(label),
        value=value,
        unit=unit,
        raw_text=raw_text,
    )


def clean_label(label: str) -> str:
    cleaned_label = " ".join(label.strip(" -_:").split())
    return cleaned_label or "value"
