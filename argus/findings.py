"""Review findings: severity ranking and report rendering."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "nit": 4}
SARIF_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "nit": "note",
}


@dataclass
class Finding:
    """A single review finding."""

    file: str
    line: int | None
    severity: str
    category: str
    title: str
    description: str
    suggestion: str = ""

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_ORDER:
            raise ValueError(f"unknown severity {self.severity!r}")


def rank_findings(findings: list[Finding]) -> list[Finding]:
    """Sort by severity (worst first), then file, then line."""
    return sorted(
        findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line or 0)
    )


def to_markdown(findings: list[Finding], pr_title: str = "") -> str:
    """Render findings as a Markdown PR comment."""
    header = "## Argus review" + (f": {pr_title}" if pr_title else "")
    lines = [header, ""]
    if not findings:
        lines.append("No issues found. Ship it.")
        return "\n".join(lines) + "\n"
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in findings:
        counts[f.severity] += 1
    summary = ", ".join(f"{n} {s}" for s, n in counts.items() if n)
    lines.append(f"**{len(findings)} findings** ({summary})")
    lines.append("")
    for f in rank_findings(findings):
        loc = f"`{f.file}`" + (f":{f.line}" if f.line else "")
        lines.append(f"### [{f.severity}] {f.title}")
        lines.append(f"{loc} · {f.category}")
        lines.append("")
        lines.append(f.description)
        if f.suggestion:
            lines.append("")
            lines.append(f"**Suggestion:** {f.suggestion}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_json(findings: list[Finding]) -> str:
    """Render findings as JSON."""
    return json.dumps([asdict(f) for f in rank_findings(findings)], indent=2) + "\n"


def to_sarif(findings: list[Finding], tool_version: str = "0.1.0") -> str:
    """Render findings as SARIF 2.1.0 for GitHub code scanning."""
    rules: list[dict[str, object]] = []
    seen: set[str] = set()
    for f in rank_findings(findings):
        rule_id = f"argus/{f.category}"
        if rule_id not in seen:
            seen.add(rule_id)
            rules.append(
                {
                    "id": rule_id,
                    "name": f.category,
                    "shortDescription": {
                        "text": f"Argus review finding: {f.category}"
                    },
                }
            )
    results: list[dict[str, object]] = []
    for f in rank_findings(findings):
        region: dict[str, object] = {"startLine": f.line} if f.line else {}
        message = f"{f.title}\n\n{f.description}"
        if f.suggestion:
            message += f"\n\nSuggestion: {f.suggestion}"
        results.append(
            {
                "ruleId": f"argus/{f.category}",
                "level": SARIF_LEVEL[f.severity],
                "message": {"text": message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.file},
                            "region": region,
                        }
                    }
                ],
                "properties": {"severity": f.severity},
            }
        )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "argus",
                        "version": tool_version,
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2) + "\n"
