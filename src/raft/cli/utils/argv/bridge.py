"""Bind peeled ``--env`` values for ``RaftCLICommands.apply``."""

from contextvars import Token
from typing import Optional, Sequence

from .overrides import ApplyEnvOverrides
from .peeler import RepeatableFlagPeeler


class ApplyEnvArgvBridge:
    """Peel repeatable ``--env`` and bind them for ``RaftCLICommands.apply`` to read."""

    FLAG = "--env"

    def __init__(
        self,
        *,
        peeler: Optional[RepeatableFlagPeeler] = None,
    ) -> None:
        self._peeler = peeler if peeler is not None else RepeatableFlagPeeler()

    def bind(self, raw: Sequence[str]) -> tuple[list[str], Token]:
        """Return ``(remaining_argv, reset_token)`` after peeling ``--env``."""
        env_overrides, remaining = self._peeler.peel(raw, self.FLAG)
        token = ApplyEnvOverrides.set(env_overrides)
        return remaining, token

    @staticmethod
    def reset(token: Token) -> None:
        ApplyEnvOverrides.reset(token)
