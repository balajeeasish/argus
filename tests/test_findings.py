"""Tests for finding ranking and report rendering."""

import json

import pytest

from argus.findings import (
    Finding,
    rank_findings,
    to_json,
    to_markdown,
    to_sarif,
)


def make_finding(severity: str = "medium", **kwargs) -> Finding:  # type: ignore[no-untyped-def]
    base = {
        "file": "a.py",
        "line": 10,
        "severity": severity,
        "category": "correctness",
        "title": "T",
        "description": "D",
    }
    base.update(kwargs)
    return Finding(**base)  # type: ignore[arg-type]


def test_ranking_orders_by_severity_then_file() -> None:
    findings = [
        make_finding("low", file="z.py"),
        make_finding("critical", file="b.py"),
        make_finding("high", file="a.py"),
    ]
    ranked = rank_findings(findings)
    assert [f.severity for f in ranked] == ["critical", "high", "low"]


def test_unknown_severity_rejected() -> None:
    with pytest.raises(ValueError, match="unknown severity"):
        make_finding("extreme")


def test_markdown_empty() -> None:
    out = to_markdown([])
    assert "No issues found" in out


def test_markdown_lists_findings_worst_first() -> None:
    findings = [make_finding("low", title="Minor"), make_finding("high", title="Bad")]
    out = to_markdown(findings, pr_title="Fix things")
    assert "Fix things" in out
    assert out.index("Bad") < out.index("Minor")
    assert "**Suggestion:**" not in out
    with_suggestion = make_finding("high", suggestion="Do X instead")
    assert "**Suggestion:** Do X instead" in to_markdown([with_suggestion])


def test_json_round_trip() -> None:
    findings = [make_finding("high")]
    data = json.loads(to_json(findings))
    assert data[0]["severity"] == "high"
    assert data[0]["title"] == "T"


def test_sarif_shape() -> None:
    findings = [make_finding("critical"), make_finding("nit", line=None)]
    sarif = json.loads(to_sarif(findings))
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "argus"
    levels = {r["properties"]["severity"]: r["level"] for r in run["results"]}
    assert levels == {"critical": "error", "nit": "note"}
    assert len(run["results"]) == 2
