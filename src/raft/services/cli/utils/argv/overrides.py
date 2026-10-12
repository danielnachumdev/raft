"""ContextVar store for peeled ``--env`` values."""

from contextvars import ContextVar, Token
from typing import Sequence


class ApplyEnvOverrides:
    """ContextVar store for ``--env`` values peeled before Fire sees argv."""

    _VALUES: ContextVar[tuple[str, ...]] = ContextVar(
        "raft_apply_env_overrides",
        default=(),
    )

    @classmethod
    def set(cls, values: Sequence[str]) -> Token:
        return cls._VALUES.set(tuple(values))

    @classmethod
    def get(cls) -> tuple[str, ...]:
        return cls._VALUES.get()

    @classmethod
    def reset(cls, token: Token) -> None:
        cls._VALUES.reset(token)
