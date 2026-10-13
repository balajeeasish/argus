"""Command-line interface: ``argus review``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .config import SEVERITIES, ReviewConfig
from .findings import to_json, to_markdown, to_sarif
from .gate import ReviewGateError, gate
from .github import GitHubClient, GitHubError
from .reviewer import ModelConfig, Reviewer, ReviewError


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (kept separate for testability)."""
    p = argparse.ArgumentParser(
        prog="argus", description="Local-first AI code reviewer for pull requests"
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("review", help="Review a pull request or a diff file")
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--pr", type=int, help="PR number (requires --repo)")
    src.add_argument("--diff-file", help="Path to a unified diff file")
    r.add_argument("--repo", help="owner/repo (required with --pr)")
    r.add_argument(
        "--guidelines",
        default=".argus.yml",
        help="Review config file (default: .argus.yml if present)",
    )
    r.add_argument("--format", choices=["md", "json", "sarif"], default="md")
    r.add_argument("--output", "-o", help="Write the report to a file")
    r.add_argument(
        "--fail-on",
        choices=[*SEVERITIES, "none"],
        help="Override the severity gate threshold from the config",
    )
    r.add_argument("--no-gate", action="store_true", help="Skip the fail-closed gate")
    r.add_argument(
        "--post-comment",
        action="store_true",
        help="Post the Markdown report as a PR comment (requires --repo/--pr)",
    )
    r.add_argument("--model", help="Model id (or set ARGUS_MODEL)")
    r.add_argument(
        "--provider",
        choices=["anthropic", "openai-compatible"],
        default="anthropic",
        help="Model provider (default: anthropic)",
    )
    return p


def load_guidelines(path: str) -> ReviewConfig:
    """Load ``.argus.yml`` when present, otherwise use defaults."""
    if os.path.exists(path):
        return ReviewConfig.from_yaml(path)
    return ReviewConfig()


def _run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.pr is not None and not args.repo:
        parser.error("--pr requires --repo")
    if args.post_comment and (not args.repo or args.pr is None):
        parser.error("--post-comment requires --repo and --pr")

    config = load_guidelines(args.guidelines)
    if args.fail_on:
        config.fail_on = args.fail_on

    gh = GitHubClient()
    if args.diff_file:
        diff = Path(args.diff_file).read_text(encoding="utf-8")
        pr_title = ""
    else:
        assert args.repo is not None  # guaranteed by the check above
        diff = gh.get_diff(args.repo, args.pr)
        pr_title = gh.get_pr_title(args.repo, args.pr)

    reviewer = Reviewer(ModelConfig(provider=args.provider, model=args.model))
    findings = reviewer.review(diff, pr_title, config)

    reports = {
        "md": to_markdown(findings, pr_title),
        "json": to_json(findings),
        "sarif": to_sarif(findings),
    }
    report = reports[args.format]
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    if args.post_comment:
        assert args.repo is not None and args.pr is not None
        gh.post_comment(args.repo, args.pr, to_markdown(findings, pr_title))

    if not args.no_gate:
        gate(findings, config.fail_on)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args, parser)
    except (GitHubError, ReviewError, ReviewGateError, ValueError) as exc:
        print(f"argus: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
