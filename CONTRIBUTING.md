# Contributing

Small, focused PRs welcome. A few ground rules:

- `mypy --strict` must pass on `argus/`, `ruff check` on everything.
- New behavior needs tests; coverage gate is 90%.
- Keep dependencies boring. A new dependency needs a justification in the PR.
- Fail closed: API errors and bad model output must raise, never silently pass.

```bash
pip install -e ".[dev]"
python -m pytest --cov=argus --cov-fail-under=90 -q
ruff check argus tests
mypy --strict argus
```
