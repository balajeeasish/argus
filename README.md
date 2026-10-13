# Argus — local-first AI code reviewer for pull requests

![build](https://github.com/balajeeasish/argus/actions/workflows/ci.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

Argus is the local-first, open-source answer to hosted AI code reviewers.
Your diffs go only to the model provider *you* choose — no third-party
cloud in the middle, no data retention you didn't agree to. Findings come
out as Markdown, JSON, or SARIF 2.1.0, and a fail-closed gate can block
merges when the review finds real problems.

## Quickstart

```bash
pip install "git+https://github.com/balajeeasish/argus.git"

export ARGUS_API_KEY="..."      # or ANTHROPIC_API_KEY / OPENAI_API_KEY
export ARGUS_MODEL="..."        # e.g. your preferred Claude or GPT model
export GITHUB_TOKEN="..."       # for --pr mode and --post-comment

# Review a PR, post the report as a comment, fail CI on high+ findings
argus review --repo owner/repo --pr 123 --post-comment

# Review a local diff file instead
argus review --diff-file changes.diff --format sarif -o results.sarif
```

## GitHub Action

```yaml
# .github/workflows/review.yml
name: review
on:
  pull_request:
    types: [opened, synchronize]
permissions:
  contents: read
  pull-requests: write
  security-events: write
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: balajeeasish/argus@v0.1.0
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          api-key: ${{ secrets.ARGUS_API_KEY }}
```

The action posts the Markdown report as a PR comment, uploads SARIF to
code scanning, and fails the check when findings breach `fail-on`.

## Configuration

Drop a `.argus.yml` in your repo to tune the reviewer:

```yaml
focus_areas:
  - security
  - concurrency
custom_rules:
  - "No raw SQL; use the query builder."
  - "All public functions need type annotations."
style: concise        # or: detailed
fail_on: high        # critical|high|medium|low|nit|none
max_findings: 30
ignore_paths: []
```

## CLI reference

```
argus review --pr 123 --repo owner/repo   # review a PR
argus review --diff-file changes.diff     # review a local diff
  --guidelines .argus.yml                 # config file (default if present)
  --format md|json|sarif                  # report format (default: md)
  --output report.md                      # write to file instead of stdout
  --fail-on high                          # override the gate threshold
  --no-gate                               # skip the gate, report only
  --post-comment                          # post Markdown report as PR comment
  --provider anthropic                    # or: openai-compatible
  --model ...                             # or set ARGUS_MODEL
```

Providers: `anthropic` (default) and any OpenAI-compatible endpoint via
`--provider openai-compatible` with `ARGUS_BASE_URL`.

## Design principles

- **Local-first.** Your code goes to exactly one place: the model provider
  you configured. No intermediary SaaS, no analytics, no retention.
- **Boring technology.** Python, `requests`, `pyyaml`. A review tool must be
  auditable itself.
- **Fail closed.** API errors and unparseable model output raise instead of
  producing an empty "all clear". The gate blocks on severity, never on vibes.
- **Machine-readable.** SARIF 2.1.0 output plugs straight into GitHub code
  scanning and any SARIF consumer.

## Roadmap

- Inline review comments on the exact diff lines (today: one summary comment)
- Repo-aware context (related files, not just the diff)
- Pinned action versions and a PyPI release

## License

MIT. See [LICENSE](LICENSE).
