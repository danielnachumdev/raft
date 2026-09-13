"""CLI package for raft (Google Fire).

Usage:
    uv run raft apply --file .raft/app.yaml
    uv run raft apply --git git@github.com:org/repo.git --ref main
    uv run raft get apps
    uv run raft delete app <name>
    uv run raft up | down | sync | redeploy | render | doctor | auth
"""

from .auth import AuthCLI
from .entry import (
    _ensure_logging_bootstrap,
    _suggest_doctor,
    main,
    run,
)
from .root import RaftCLI

__all__ = [
    "AuthCLI",
    "RaftCLI",
    "_ensure_logging_bootstrap",
    "_suggest_doctor",
    "main",
    "run",
]
