"""config — optional per-repo configuration. Zero-dependency (stdlib ``json``).

The whole point of Platão is that the questions are an obligation, not a menu you switch off when
inconvenient — but some checks genuinely don't fit some repos, so you can turn specific ones off.
Drop a ``.platao.json`` at your repo root:

    { "disable": ["ui_marble_tokens", "debt_tracked"] }

Every finding whose ``check_id`` is listed is dropped. No file = nothing disabled (the default).
A YAML file with question packs is planned; this JSON form is the real thing today.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_NAMES = (".platao.json",)


@dataclass(slots=True)
class Config:
    """Loaded repo configuration. Empty (nothing disabled) when there is no config file."""

    disable: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, root: Path) -> Config:
        """Read ``.platao.json`` from ``root``. Malformed/unreadable config degrades to defaults."""
        for name in _CONFIG_NAMES:
            path = root / name
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return cls()
            if isinstance(data, dict):
                disable = data.get("disable") or []
                if isinstance(disable, list):
                    return cls(disable={str(x) for x in disable})
            return cls()
        return cls()
