"""Minimal GitHub client: fetch PR diffs, post review comments."""

from __future__ import annotations

import os
from typing import Any

import requests

API_BASE = "https://api.github.com"


class GitHubError(Exception):
    """A GitHub API call failed."""


class GitHubClient:
    """Thin wrapper over the GitHub REST API for PR review workflows."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def _get(self, path: str, accept: str | None = None) -> requests.Response:
        headers = {"Accept": accept} if accept else None
        resp = self.session.get(f"{API_BASE}{path}", headers=headers, timeout=60)
        if resp.status_code != 200:
            raise GitHubError(
                f"GET {path} failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp

    def get_diff(self, repo: str, pr_number: int) -> str:
        """Return the unified diff for a pull request."""
        resp = self._get(
            f"/repos/{repo}/pulls/{pr_number}", accept="application/vnd.github.diff"
        )
        return resp.text

    def get_pr_title(self, repo: str, pr_number: int) -> str:
        """Return the title of a pull request."""
        data: Any = self._get(f"/repos/{repo}/pulls/{pr_number}").json()
        return str(data.get("title", ""))

    def post_comment(self, repo: str, pr_number: int, body: str) -> dict[str, Any]:
        """Post a Markdown comment on a pull request."""
        resp = self.session.post(
            f"{API_BASE}/repos/{repo}/issues/{pr_number}/comments",
            json={"body": body},
            timeout=60,
        )
        if resp.status_code not in (200, 201):
            raise GitHubError(
                f"POST comment failed: {resp.status_code} {resp.text[:200]}"
            )
        result: dict[str, Any] = resp.json()
        return result
