"""Tests for CLI wiring (no network; reviewer is stubbed)."""

import json

import pytest

from argus import cli
from argus.config import ReviewConfig
from argus.findings import Finding


def test_load_guidelines_missing_file_uses_defaults(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    assert cli.load_guidelines(".argus.yml") == ReviewConfig()


def test_load_guidelines_reads_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "custom.yml"
    p.write_text("fail_on: low\n")
    assert cli.load_guidelines(str(p)).fail_on == "low"


def test_parser_requires_source() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["review"])


def test_parser_pr_requires_repo_flag_shape() -> None:
    args = cli.build_parser().parse_args(["review", "--pr", "1", "--repo", "o/r"])
    assert args.pr == 1 and args.repo == "o/r"


def test_run_pr_requires_repo() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["review", "--diff-file", "x.diff"])
    # --diff-file path needs no repo; simulate the --pr-without---repo error path
    bad = parser.parse_args(["review", "--pr", "5"])
    with pytest.raises(SystemExit):
        cli._run(bad, parser)
    assert args.diff_file == "x.diff"


def test_run_end_to_end_with_stubbed_reviewer(tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    diff_file = tmp_path / "change.diff"
    diff_file.write_text("diff --git a/a.py b/a.py\n")

    findings = [
        Finding(
            file="a.py",
            line=1,
            severity="low",
            category="style",
            title="Nit",
            description="d",
        )
    ]

    class StubReviewer:
        def __init__(self, *a, **k) -> None:  # type: ignore[no-untyped-def]
            pass

        def review(self, *a, **k) -> list[Finding]:  # type: ignore[no-untyped-def]
            return findings

    monkeypatch.setattr(cli, "Reviewer", StubReviewer)
    monkeypatch.setattr(
        cli, "ModelConfig", lambda **k: object()  # type: ignore[no-untyped-def]
    )
    monkeypatch.setenv("ARGUS_MODEL", "x")
    monkeypatch.setenv("ARGUS_API_KEY", "x")

    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "review",
            "--diff-file",
            str(diff_file),
            "--format",
            "json",
            "--no-gate",
            "--guidelines",
            "/nonexistent.yml",
        ]
    )
    assert cli._run(args, parser) == 0
    out = capsys.readouterr().out
    assert json.loads(out)[0]["severity"] == "low"


def test_gate_failure_returns_nonzero(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    diff_file = tmp_path / "change.diff"
    diff_file.write_text("diff")

    findings = [
        Finding(
            file="a.py",
            line=1,
            severity="critical",
            category="security",
            title="Bad",
            description="d",
        )
    ]

    class StubReviewer:
        def __init__(self, *a, **k) -> None:  # type: ignore[no-untyped-def]
            pass

        def review(self, *a, **k) -> list[Finding]:  # type: ignore[no-untyped-def]
            return findings

    monkeypatch.setattr(cli, "Reviewer", StubReviewer)
    monkeypatch.setattr(cli, "ModelConfig", lambda **k: object())  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ARGUS_MODEL", "x")
    monkeypatch.setenv("ARGUS_API_KEY", "x")

    # Gate failure surfaces as exit code 1 from main(); _run itself raises.
    assert (
        cli.main(
            [
                "review",
                "--diff-file",
                str(diff_file),
                "--guidelines",
                "/nonexistent.yml",
            ]
        )
        == 1
    )
    parser = cli.build_parser()
    args = parser.parse_args(
        ["review", "--diff-file", str(diff_file), "--guidelines", "/nonexistent.yml"]
    )
    with pytest.raises(cli.ReviewGateError):
        cli._run(args, parser)
