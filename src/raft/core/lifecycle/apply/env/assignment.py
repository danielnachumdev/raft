"""Parse and normalize ``KEY=VALUE`` assignments from CLI / dotenv text."""

import re
from typing import Sequence, Union

from raft.core.core.errors.cta import OperatorError

ASSIGN_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

EnvOverrides = Union[None, str, Sequence[str]]


class EnvAssignment:
    """Parse and normalize ``KEY=VALUE`` assignments from CLI / dotenv text."""

    @classmethod
    def parse(cls, raw: str) -> tuple[str, str]:
        """Parse a single ``KEY=VALUE`` (optional ``export``) from ``--env``."""
        match = ASSIGN_RE.match(raw.strip())
        if match is None:
            raise cls._bad_assignment(raw)
        return match.group(1), match.group(2)

    @classmethod
    def normalize_flags(cls, env: EnvOverrides) -> list[str]:
        """Fire may pass a single ``--env`` as str or repeated flags as a sequence."""
        if env is None:
            return []
        if isinstance(env, str):
            return [env]
        return list(env)

    @staticmethod
    def _bad_assignment(raw: str) -> OperatorError:
        return OperatorError(
            f"invalid --env value {raw!r} (expected KEY=VALUE)\n"
            f"Fix: pass --env NAME=value (NAME matching [A-Za-z_][A-Za-z0-9_]*)"
        )
