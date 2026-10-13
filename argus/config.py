"""Review configuration: guidelines, severity policy, and review style."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

SEVERITIES = ("critical", "high", "medium", "low", "nit")
STYLES = ("concise", "detailed")


@dataclass
class ReviewConfig:
    """Tunable review behavior, loadable from ``.argus.yml``."""

    focus_areas: list[str] = field(default_factory=list)
    custom_rules: list[str] = field(default_factory=list)
    style: str = "concise"
    fail_on: str = "high"
    max_findings: int = 30
    ignore_paths: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.style not in STYLES:
            raise ValueError(f"style must be one of {STYLES}, got {self.style!r}")
        if self.fail_on != "none" and self.fail_on not in SEVERITIES:
            raise ValueError(
                f"fail_on must be one of {SEVERITIES} or 'none', got {self.fail_on!r}"
            )
        for name in ("focus_areas", "custom_rules", "ignore_paths"):
            values = getattr(self, name)
            if not isinstance(values, list) or not all(
                isinstance(v, str) for v in values
            ):
                raise ValueError(
                    f"{name} must be a list of strings, got {values!r} "
                    "(check your YAML quoting — 'key: value' lines parse as mappings)"
                )
        if not isinstance(self.max_findings, int) or self.max_findings < 1:
            raise ValueError(
                f"max_findings must be a positive integer, got {self.max_findings!r}"
            )

    @classmethod
    def from_yaml(cls, path: str | Path) -> ReviewConfig:
        """Load config from a YAML file; unknown keys are rejected loudly."""
        raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: expected a YAML mapping at the top level")
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"{path}: unknown keys: {sorted(unknown)}")
        return cls(**{k: v for k, v in raw.items() if k in known})
