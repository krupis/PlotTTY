"""Extract numeric values from serial text."""

from __future__ import annotations

import re
from collections.abc import Iterable
from time import time

from .models import CapturedValue, ExtractionRule


NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
AUTO_KEY_VALUE_RE = re.compile(
    rf"([A-Za-z_][\w .\-/]*)\s*(?:=|:)\s*({NUMBER_PATTERN})\s*"
    rf"((?![A-Za-z_][\w.\-/]*\s*(?:=|:))[^\s,;=:]*)?"
)
FIRST_NUMBER_RE = re.compile(NUMBER_PATTERN)


class ExtractionEngine:
    """Apply enabled extraction rules to one text line."""

    def __init__(self, rules: Iterable[ExtractionRule] | None = None):
        self.rules = default_rules() if rules is None else list(rules)

    def extract(self, text: str, timestamp: float | None = None) -> list[CapturedValue]:
        timestamp = timestamp if timestamp is not None else time()
        # Split once per delimiter, shared by counter and value rules for this line.
        fields: dict[str, list[str]] = {}
        counter_timestamp = _counter_timestamp(self.rules, text, fields)
        timestamp = counter_timestamp if counter_timestamp is not None else timestamp
        captured_values = []

        for rule in self.rules:
            if not rule.enabled or rule.sample_counter:
                continue

            captured_values.extend(_extract_rule(rule, text, timestamp, fields))

        return captured_values


def default_rules() -> list[ExtractionRule]:
    return [ExtractionRule(label="Auto key/value", mode="auto_key_value")]


def _extract_rule(
    rule: ExtractionRule, text: str, timestamp: float, fields: dict[str, list[str]]
) -> list[CapturedValue]:
    captured_values = []

    if rule.mode == "auto_key_value":
        for match in AUTO_KEY_VALUE_RE.finditer(text):
            label = match.group(1)
            value = float(match.group(2))
            unit = (match.group(3) or rule.unit or "").strip()
            captured_values.append(_captured_value(timestamp, label, value, unit, text))

    elif rule.mode == "first_number":
        match = FIRST_NUMBER_RE.search(text)
        if match:
            value = float(match.group(0))
            captured_values.append(_captured_value(timestamp, rule.label, value, rule.unit, text))

    elif rule.mode == "regex" and rule.extra_setting:
        for match in re.finditer(rule.extra_setting, text):
            if match.groups():
                captured_values.append(
                    _captured_value(timestamp, rule.label, float(match.group(1)), rule.unit, text)
                )

    elif rule.mode == "delimiter_column":
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


def _counter_timestamp(
    rules: Iterable[ExtractionRule], text: str, fields: dict[str, list[str]]
) -> float | None:
    for rule in rules:
        if not rule.sample_counter:
            continue

        values = _extract_rule(rule, text, 0.0, fields)
        if values:
            return values[0].value

    return None


def _captured_value(timestamp: float, label: str, value: float, unit: str, raw_text: str) -> CapturedValue:
    return CapturedValue(
        timestamp=timestamp,
        label=_clean_label(label),
        value=value,
        unit=unit,
        raw_text=raw_text,
    )


def _clean_label(label: str) -> str:
    cleaned_label = " ".join(label.strip(" -_:").split())
    return cleaned_label or "value"
