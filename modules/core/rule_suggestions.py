"""Suggest extraction rules from example serial text."""

from __future__ import annotations

import re

from .extraction import AUTO_KEY_VALUE_RE, FIRST_NUMBER_RE, NUMBER_PATTERN, clean_label
from .models import ExtractionRule


DELIMITER_SPLIT_RE = re.compile(r"[,;\t]")


def suggest_rules(text: str) -> list[ExtractionRule]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    suggestions = _key_value_suggestions(lines)
    if suggestions:
        return suggestions

    suggestions = _delimiter_suggestions(lines)
    if suggestions:
        return suggestions

    return _first_number_suggestion(lines)


def _key_value_suggestions(lines: list[str]) -> list[ExtractionRule]:
    suggestions = []
    seen_labels = set()

    for line in lines:
        for match in AUTO_KEY_VALUE_RE.finditer(line):
            label = clean_label(match.group(1))
            if label in seen_labels:
                continue
            seen_labels.add(label)
            regex_pattern = rf"{re.escape(label)}\s*(?:=|:)\s*({NUMBER_PATTERN})"
            suggestions.append(
                ExtractionRule(label=label, mode="regex", extra_setting=regex_pattern,
                               unit=(match.group(3) or "").strip())
            )

    return suggestions


def _delimiter_suggestions(lines: list[str]) -> list[ExtractionRule]:
    first_delimited_line = next((line for line in lines if DELIMITER_SPLIT_RE.search(line)), "")
    if not first_delimited_line:
        return []

    delimiter = _detect_delimiter(first_delimited_line)
    if not delimiter:
        return []

    parts = [part.strip() for part in first_delimited_line.split(delimiter)]
    numeric_columns = []
    for index, part in enumerate(parts):
        if FIRST_NUMBER_RE.search(part):
            numeric_columns.append(index)

    if len(numeric_columns) < 2:
        return []

    suggestions = []
    for index in numeric_columns:
        suggestions.append(
            ExtractionRule(
                label=f"Value {index}",
                mode="delimiter_column",
                extra_setting=str(index),
                delimiter=delimiter,
            )
        )
    return suggestions


def _first_number_suggestion(lines: list[str]) -> list[ExtractionRule]:
    for line in lines:
        if FIRST_NUMBER_RE.search(line):
            return [ExtractionRule(label="Value", mode="first_number")]
    return []


def _detect_delimiter(line: str) -> str:
    for delimiter in (",", ";", "\t"):
        if delimiter in line:
            return delimiter
    return ""
