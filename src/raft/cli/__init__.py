"""CLI package for raft (Google Fire).

Usage:
    raft apply --file .raft/app.yaml
    raft apply --git git@github.com:org/repo.git --ref main
    raft get apps
    raft delete app <name>
    raft up | down | sync | redeploy | render | doctor | update | auth
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
