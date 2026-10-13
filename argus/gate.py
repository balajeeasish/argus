"""Fail-closed CI gate: block the build when findings breach the severity bar."""

from __future__ import annotations

from .findings import SEVERITY_ORDER, Finding


class ReviewGateError(Exception):
    """Raised when review findings breach the configured severity threshold."""


def gate(findings: list[Finding], fail_on: str) -> None:
    """Raise ReviewGateError if any finding meets or exceeds ``fail_on``.

    ``fail_on="none"`` disables the gate. Anything else must be a valid
    severity; unknown values raise ValueError rather than silently passing.
    """
    if fail_on == "none":
        return
    if fail_on not in SEVERITY_ORDER:
        raise ValueError(f"unknown severity {fail_on!r}")
    bar = SEVERITY_ORDER[fail_on]
    blocking = [f for f in findings if SEVERITY_ORDER[f.severity] <= bar]
    if blocking:
        raise ReviewGateError(
            f"{len(blocking)} finding(s) at or above '{fail_on}' severity "
            "- review gate failed"
        )
