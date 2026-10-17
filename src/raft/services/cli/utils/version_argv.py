"""Detect ``raft --version`` / ``-V`` / ``version`` before Fire dispatch."""

from typing import Sequence


class VersionArgv:
    """True when argv is solely a version request (no stack load needed)."""

    _TOKENS = frozenset({"--version", "-V", "version"})

    @classmethod
    def is_request(cls, argv: Sequence[str]) -> bool:
        args = [a for a in argv if a != "--"]
        return len(args) == 1 and args[0] in cls._TOKENS
