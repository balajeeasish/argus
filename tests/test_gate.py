"""Tests for the fail-closed review gate."""

import pytest

from argus.findings import Finding
from argus.gate import ReviewGateError, gate


def finding(severity: str) -> Finding:
    return Finding(
        file="a.py",
        line=1,
        severity=severity,
        category="correctness",
        title="T",
        description="D",
    )


def test_gate_blocks_at_or_above_threshold() -> None:
    with pytest.raises(ReviewGateError):
        gate([finding("high")], "high")
    with pytest.raises(ReviewGateError):
        gate([finding("critical")], "high")


def test_gate_passes_below_threshold() -> None:
    gate([finding("medium"), finding("low")], "high")  # no raise


def test_gate_empty_findings_pass() -> None:
    gate([], "critical")  # no raise


def test_gate_none_disables() -> None:
    gate([finding("critical")], "none")  # no raise


def test_gate_rejects_unknown_threshold() -> None:
    with pytest.raises(ValueError, match="unknown severity"):
        gate([], "extreme")
