"""JSON profile persistence for PlotTTY settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import ExtractionRule
from .serial_transport import SerialSettings


@dataclass
class PlotTTYProfile:
    name: str = "Untitled Profile"
    serial: SerialSettings = field(default_factory=SerialSettings)
    commands: list[str] = field(default_factory=list)
    rules: list[ExtractionRule] = field(default_factory=list)


def load_profile(path: str | Path) -> PlotTTYProfile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return profile_from_dict(data)


def save_profile(profile: PlotTTYProfile, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


def profile_from_dict(data: dict[str, Any]) -> PlotTTYProfile:
    serial = SerialSettings(**data.get("serial", {}))
    rules = [ExtractionRule(**_rule_from_dict(item)) for item in data.get("rules", [])]
    commands = list(data.get("commands", []))
    return PlotTTYProfile(
        name=data.get("name", "Untitled Profile"),
        serial=serial,
        commands=commands,
        rules=rules,
    )


def _rule_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    rule = dict(data)
    if "pattern" in rule and "extra_setting" not in rule:
        rule["extra_setting"] = rule.pop("pattern")
    return rule
