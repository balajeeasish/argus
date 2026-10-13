"""LLM review engine: prompt building, provider adapters, finding parsing."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from .config import ReviewConfig
from .findings import SEVERITY_ORDER, Finding

JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class ReviewError(Exception):
    """The model call failed or its output could not be parsed."""


def build_prompt(diff: str, pr_title: str, config: ReviewConfig) -> str:
    """Assemble the review prompt from guidelines and the diff."""
    lines = [
        "You are Argus, a senior code reviewer. Review the pull-request diff below.",
        "Return ONLY a JSON object of the form:",
        '{"findings": [{"file": "path/to/file.py", "line": 12,',
        ' "severity": "critical|high|medium|low|nit", "category": "correctness",',
        ' "title": "short title", "description": "what is wrong and why",',
        ' "suggestion": "how to fix it"}]}',
        "",
        "Rules:",
        "- Report real issues only. No praise.",
        "- No style nitpicks unless they hurt readability.",
        f"- Return at most {config.max_findings} findings, ranked by severity.",
        "- severity guide: critical = exploitable/security/data-loss;",
        "- high = likely bug; medium = real but limited blast radius;",
        "- low = minor; nit = polish.",
    ]
    if config.focus_areas:
        lines.append("- Focus especially on: " + ", ".join(config.focus_areas))
    if config.custom_rules:
        lines.append("- Repository rules (treat as binding):")
        lines.extend(f"  - {rule}" for rule in config.custom_rules)
    if config.style == "detailed":
        lines.append("- Explain the why behind each finding, not just the what.")
    else:
        lines.append("- Keep descriptions to 2-3 sentences.")
    if pr_title:
        lines.append("")
        lines.append(f"PR title: {pr_title}")
    lines += ["", "Diff:", diff]
    return "\n".join(lines)


def parse_findings(text: str) -> list[Finding]:
    """Parse the model's JSON output into Finding objects. Strict, never silent."""
    payload = text.strip()
    fence = JSON_FENCE.search(payload)
    if fence:
        payload = fence.group(1)
    try:
        data: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReviewError(f"model did not return valid JSON: {exc}") from exc
    items = data.get("findings") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ReviewError("model JSON had no 'findings' list")
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        line = item.get("line")
        severity = str(item.get("severity", "medium")).lower()
        if severity not in SEVERITY_ORDER:
            severity = "medium"
        findings.append(
            Finding(
                file=str(item.get("file", "unknown")),
                line=(
                    int(line)
                    if isinstance(line, int)
                    or (isinstance(line, str) and line.isdigit())
                    else None
                ),
                severity=severity,
                category=str(item.get("category", "general")),
                title=str(item["title"]),
                description=str(item.get("description", "")),
                suggestion=str(item.get("suggestion", "")),
            )
        )
    return findings


@dataclass
class ModelConfig:
    """Which model to call. Values fall back to ARGUS_* environment variables."""

    provider: str = "anthropic"  # or "openai-compatible"
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 120


class Reviewer:
    """Runs a review: builds the prompt, calls the model, parses findings."""

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        session: requests.Session | None = None,
    ) -> None:
        cfg = model_config or ModelConfig()
        if cfg.provider not in ("anthropic", "openai-compatible"):
            raise ReviewError(
                f"unknown provider {cfg.provider!r}: "
                "use 'anthropic' or 'openai-compatible'"
            )
        model = cfg.model or os.environ.get("ARGUS_MODEL", "")
        if not model:
            raise ReviewError(
                "no model configured: pass model=... or set the ARGUS_MODEL "
                "environment variable"
            )
        default_key_env = (
            "ANTHROPIC_API_KEY" if cfg.provider == "anthropic" else "OPENAI_API_KEY"
        )
        api_key = (
            cfg.api_key
            or os.environ.get("ARGUS_API_KEY", "")
            or os.environ.get(default_key_env, "")
        )
        if not api_key:
            raise ReviewError(
                "no API key configured: set ARGUS_API_KEY "
                f"(or {default_key_env})"
            )
        default_base = (
            "https://api.anthropic.com"
            if cfg.provider == "anthropic"
            else "https://api.openai.com/v1"
        )
        base_url = (
            cfg.base_url or os.environ.get("ARGUS_BASE_URL", "") or default_base
        ).rstrip("/")
        self.config = ModelConfig(
            provider=cfg.provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            timeout=cfg.timeout,
        )
        self.session = session or requests.Session()

    def review(
        self, diff: str, pr_title: str, config: ReviewConfig
    ) -> list[Finding]:
        """Review a unified diff and return ranked findings."""
        prompt = build_prompt(diff, pr_title, config)
        return parse_findings(self._complete(prompt))

    def _complete(self, prompt: str) -> str:
        cfg = self.config
        system = "You are a precise, senior code reviewer."
        if cfg.provider == "anthropic":
            url = f"{cfg.base_url}/v1/messages"
            headers = {
                "x-api-key": cfg.api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            body: dict[str, Any] = {
                "model": cfg.model,
                "max_tokens": 4096,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
        else:
            url = f"{cfg.base_url}/chat/completions"
            headers = {
                "authorization": f"Bearer {cfg.api_key or ''}",
                "content-type": "application/json",
            }
            body = {
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }
        try:
            resp = self.session.post(
                url, headers=headers, json=body, timeout=cfg.timeout
            )
        except requests.RequestException as exc:
            raise ReviewError(f"model request failed: {exc}") from exc
        if resp.status_code != 200:
            raise ReviewError(
                f"model API error {resp.status_code}: {resp.text[:300]}"
            )
        data: Any = resp.json()
        text = ""
        if cfg.provider == "anthropic":
            blocks = data.get("content", [])
            text = "".join(
                b.get("text", "") for b in blocks if isinstance(b, dict)
            )
        else:
            choices = data.get("choices", [])
            if choices and isinstance(choices[0], dict):
                text = str(choices[0].get("message", {}).get("content", ""))
        if not text.strip():
            raise ReviewError("model returned an empty response")
        return text
