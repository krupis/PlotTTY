"""Suggest extraction rules from example serial text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .extraction import AUTO_KEY_VALUE_RE, DELIMITER_SPLIT_RE, FIRST_NUMBER_RE, NUMBER_PATTERN
from .models import ExtractionRule


@dataclass(frozen=True)
class RuleSuggestion:
    label: str
    example_value: str
    how_found: str
    rule: ExtractionRule


def suggest_rules_from_samples(text: str) -> list[RuleSuggestion]:
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


def _key_value_suggestions(lines: list[str]) -> list[RuleSuggestion]:
    suggestions = []
    seen_labels = set()

    for line in lines:
        for match in AUTO_KEY_VALUE_RE.finditer(line):
            label = _clean_label(match.group(1))
            if label in seen_labels:
                continue
            seen_labels.add(label)
            example_value = match.group(2)
            regex_pattern = rf"{re.escape(label)}\s*(?:=|:)\s*({NUMBER_PATTERN})"
            suggestions.append(
                RuleSuggestion(
                    label=label,
                    example_value=example_value,
                    how_found=f'after "{label}"',
                    rule=ExtractionRule(label=label, mode="regex", extra_setting=regex_pattern),
                )
            )

    return suggestions


def _delimiter_suggestions(lines: list[str]) -> list[RuleSuggestion]:
    first_delimited_line = next((line for line in lines if DELIMITER_SPLIT_RE.search(line)), "")
    if not first_delimited_line:
        return []
    delimiter = _detect_delimiter(first_delimited_line)
    if not delimiter:
        return []

    parts = [part.strip() for part in first_delimited_line.split(delimiter)]
    numeric_columns = []
    for index, part in enumerate(parts):
        match = FIRST_NUMBER_RE.search(part)
        if match:
            numeric_columns.append((index, match.group(0)))

    if len(numeric_columns) < 2:
        return []

    suggestions = []
    for index, value in numeric_columns:
        label = f"Value {index + 1}"
        suggestions.append(
            RuleSuggestion(
                label=label,
                example_value=value,
                how_found=f"position {index + 1}",
                rule=ExtractionRule(
                    label=label,
                    mode="delimiter_column",
                    extra_setting=str(index),
                    delimiter=delimiter,
                ),
            )
        )
    return suggestions


def _first_number_suggestion(lines: list[str]) -> list[RuleSuggestion]:
    for line in lines:
        match = FIRST_NUMBER_RE.search(line)
        if match:
            return [
                RuleSuggestion(
                    label="Value",
                    example_value=match.group(0),
                    how_found="first number in each line",
                    rule=ExtractionRule(label="Value", mode="first_number"),
                )
            ]
    return []


def _clean_label(label: str) -> str:
    cleaned_label = " ".join(label.strip(" -_:").split())
    return cleaned_label or "Value"


def _detect_delimiter(line: str) -> str:
    for delimiter in (",", ";", "\t"):
        if delimiter in line:
            return delimiter
    return ""
