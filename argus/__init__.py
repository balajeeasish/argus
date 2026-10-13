"""Argus — local-first AI code reviewer for pull requests."""

__version__ = "0.1.0"

from .config import ReviewConfig
from .findings import Finding, rank_findings
from .gate import ReviewGateError, gate

__all__ = [
    "ReviewConfig",
    "Finding",
    "rank_findings",
    "ReviewGateError",
    "gate",
    "__version__",
]
