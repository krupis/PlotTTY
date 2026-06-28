"""JSON profile persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import ExtractionRule


@dataclass
class AppProfile:
    name: str = "Untitled Profile"
    rules: list[ExtractionRule] = field(default_factory=list)


def load_profile(path: str | Path) -> AppProfile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return profile_from_dict(data)


def save_profile(profile: AppProfile, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(profile), indent=2), encoding="utf-8")


def profile_from_dict(data: dict[str, Any]) -> AppProfile:
    rules = [ExtractionRule(**_rule_from_dict(item)) for item in data.get("rules", [])]
    return AppProfile(
        name=data.get("name", "Untitled Profile"),
        rules=rules,
    )


def _rule_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    rule = dict(data)
    if "pattern" in rule and "extra_setting" not in rule:
        rule["extra_setting"] = rule.pop("pattern")
    return rule
