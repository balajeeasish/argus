"""Tests for review configuration loading and validation."""

import pytest

from argus.config import ReviewConfig


def test_defaults() -> None:
    cfg = ReviewConfig()
    assert cfg.style == "concise"
    assert cfg.fail_on == "high"
    assert cfg.max_findings == 30
    assert cfg.focus_areas == []


def test_from_yaml(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / ".argus.yml"
    p.write_text(
        "focus_areas:\n  - security\ncustom_rules:\n  - 'No raw SQL.'\n"
        "style: detailed\nfail_on: medium\nmax_findings: 10\n"
    )
    cfg = ReviewConfig.from_yaml(p)
    assert cfg.focus_areas == ["security"]
    assert cfg.custom_rules == ["No raw SQL."]
    assert cfg.style == "detailed"
    assert cfg.fail_on == "medium"
    assert cfg.max_findings == 10


def test_from_yaml_empty_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / ".argus.yml"
    p.write_text("")
    assert ReviewConfig.from_yaml(p) == ReviewConfig()


def test_from_yaml_rejects_unknown_keys(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / ".argus.yml"
    p.write_text("bogus_key: 1\n")
    with pytest.raises(ValueError, match="unknown keys"):
        ReviewConfig.from_yaml(p)


def test_from_yaml_rejects_non_mapping(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / ".argus.yml"
    p.write_text("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        ReviewConfig.from_yaml(p)


def test_invalid_style_rejected() -> None:
    with pytest.raises(ValueError, match="style"):
        ReviewConfig(style="sassy")


def test_invalid_fail_on_rejected() -> None:
    with pytest.raises(ValueError, match="fail_on"):
        ReviewConfig(fail_on="extreme")
    # "none" is the documented way to disable the gate
    assert ReviewConfig(fail_on="none").fail_on == "none"


def test_list_fields_must_be_strings() -> None:
    # Simulates the classic YAML gotcha: "- key: value" parses as a mapping.
    with pytest.raises(ValueError, match="focus_areas must be a list of strings"):
        ReviewConfig(focus_areas=["security", {"oops": "mapping"}])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="custom_rules must be a list of strings"):
        ReviewConfig(custom_rules=[123])  # type: ignore[list-item]


def test_max_findings_must_be_positive_int() -> None:
    with pytest.raises(ValueError, match="max_findings"):
        ReviewConfig(max_findings=0)
    with pytest.raises(ValueError, match="max_findings"):
        ReviewConfig(max_findings="10")  # type: ignore[arg-type]
