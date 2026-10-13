"""Tests for the GitHub client (HTTP mocked)."""

from typing import Any

import pytest

from argus.github import GitHubClient, GitHubError


class FakeResponse:
    def __init__(self, status_code: int, text: str = "", payload: Any = None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, headers: Any = None, timeout: Any = None) -> FakeResponse:
        self.calls.append({"method": "GET", "url": url, "headers": headers})
        return self._response

    def post(
        self, url: str, json: Any = None, timeout: Any = None
    ) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, "json": json})
        return self._response


def make_client(response: FakeResponse) -> GitHubClient:
    client = GitHubClient(token="test-token")
    client.session = FakeSession(response)  # type: ignore[assignment]
    return client


def test_get_diff_uses_diff_accept_header() -> None:
    client = make_client(FakeResponse(200, text="diff --git ..."))
    diff = client.get_diff("owner/repo", 42)
    assert diff == "diff --git ..."
    call = client.session.calls[0]  # type: ignore[attr-defined]
    assert call["url"] == "https://api.github.com/repos/owner/repo/pulls/42"
    assert call["headers"]["Accept"] == "application/vnd.github.diff"


def test_get_diff_raises_on_error() -> None:
    client = make_client(FakeResponse(404, text="not found"))
    with pytest.raises(GitHubError, match="404"):
        client.get_diff("owner/repo", 42)


def test_get_pr_title() -> None:
    client = make_client(FakeResponse(200, payload={"title": "Fix the thing"}))
    assert client.get_pr_title("owner/repo", 7) == "Fix the thing"


def test_post_comment() -> None:
    client = make_client(FakeResponse(201, payload={"id": 1}))
    result = client.post_comment("owner/repo", 7, "hello")
    assert result == {"id": 1}
    call = client.session.calls[0]  # type: ignore[attr-defined]
    assert call["url"].endswith("/repos/owner/repo/issues/7/comments")
    assert call["json"] == {"body": "hello"}


def test_post_comment_raises_on_error() -> None:
    client = make_client(FakeResponse(403, text="forbidden"))
    with pytest.raises(GitHubError, match="403"):
        client.post_comment("owner/repo", 7, "hello")
