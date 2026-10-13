"""Tests for the review engine (model HTTP mocked)."""

import json
from typing import Any

import pytest

from argus.config import ReviewConfig
from argus.reviewer import (
    ModelConfig,
    Reviewer,
    ReviewError,
    build_prompt,
    parse_findings,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: Any, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        headers: Any = None,
        json: Any = None,
        timeout: Any = None,
    ) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self._response


def anthropic_response(text: str) -> FakeResponse:
    return FakeResponse(200, {"content": [{"type": "text", "text": text}]})


def openai_response(text: str) -> FakeResponse:
    return FakeResponse(
        200, {"choices": [{"message": {"content": text}}]}
    )


def findings_json() -> str:
    return json.dumps(
        {
            "findings": [
                {
                    "file": "a.py",
                    "line": 3,
                    "severity": "HIGH",
                    "category": "correctness",
                    "title": "Off by one",
                    "description": "Loop bound is wrong.",
                    "suggestion": "Use < instead of <=",
                },
                {
                    "file": "b.py",
                    "line": "not-a-line",
                    "severity": "bogus",
                    "category": "style",
                    "title": "Weird",
                    "description": "d",
                },
            ]
        }
    )


def make_reviewer(
    response: FakeResponse,
    monkeypatch: pytest.MonkeyPatch,
    provider: str = "anthropic",
    extra_env: dict[str, str] | None = None,
) -> Reviewer:
    monkeypatch.setenv("ARGUS_MODEL", "test-model")
    monkeypatch.setenv("ARGUS_API_KEY", "test-key")
    if extra_env:
        for k, v in extra_env.items():
            monkeypatch.setenv(k, v)
    return Reviewer(
        ModelConfig(provider=provider), session=FakeSession(response)  # type: ignore[arg-type]
    )


def test_parse_findings_coerces_and_skips() -> None:
    findings = parse_findings(findings_json())
    assert len(findings) == 2
    assert findings[0].severity == "high"  # lowercased
    assert findings[0].line == 3
    assert findings[1].severity == "medium"  # unknown coerced
    assert findings[1].line is None  # non-numeric line dropped


def test_parse_findings_handles_fenced_json() -> None:
    fenced = "```json\n" + findings_json() + "\n```"
    assert len(parse_findings(fenced)) == 2


def test_parse_findings_rejects_garbage() -> None:
    with pytest.raises(ReviewError, match="valid JSON"):
        parse_findings("this is not json")


def test_parse_findings_rejects_missing_list() -> None:
    with pytest.raises(ReviewError, match="findings"):
        parse_findings('{"nope": []}')


def test_reviewer_anthropic_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = make_reviewer(anthropic_response(findings_json()), monkeypatch)
    findings = reviewer.review("diff --git ...", "PR title", ReviewConfig())
    assert len(findings) == 2
    call = reviewer.session.calls[0]  # type: ignore[attr-defined]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["json"]["model"] == "test-model"


def test_reviewer_openai_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = make_reviewer(
        openai_response(findings_json()), monkeypatch, provider="openai-compatible"
    )
    findings = reviewer.review("diff", "", ReviewConfig())
    assert len(findings) == 2
    call = reviewer.session.calls[0]  # type: ignore[attr-defined]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"


def test_reviewer_respects_base_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = make_reviewer(
        openai_response(findings_json()),
        monkeypatch,
        provider="openai-compatible",
        extra_env={"ARGUS_BASE_URL": "http://localhost:1234/v1"},
    )
    reviewer.review("diff", "", ReviewConfig())
    call = reviewer.session.calls[0]  # type: ignore[attr-defined]
    assert call["url"] == "http://localhost:1234/v1/chat/completions"


def test_reviewer_raises_on_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = make_reviewer(FakeResponse(401, {}, text="bad key"), monkeypatch)
    with pytest.raises(ReviewError, match="401"):
        reviewer.review("diff", "", ReviewConfig())


def test_reviewer_raises_on_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = make_reviewer(anthropic_response("   "), monkeypatch)
    with pytest.raises(ReviewError, match="empty"):
        reviewer.review("diff", "", ReviewConfig())


def test_reviewer_requires_model_and_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("ARGUS_MODEL", raising=False)
    monkeypatch.delenv("ARGUS_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ReviewError, match="ARGUS_MODEL"):
        Reviewer(ModelConfig())


def test_reviewer_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ReviewError, match="unknown provider"):
        make_reviewer(
            anthropic_response(findings_json()), monkeypatch, provider="mystery"
        )


def test_build_prompt_includes_guidelines() -> None:
    cfg = ReviewConfig(
        focus_areas=["security"],
        custom_rules=["No raw SQL."],
        style="detailed",
        max_findings=5,
    )
    prompt = build_prompt("DIFF", "Title", cfg)
    assert "security" in prompt
    assert "No raw SQL." in prompt
    assert "at most 5 findings" in prompt
    assert "DIFF" in prompt
