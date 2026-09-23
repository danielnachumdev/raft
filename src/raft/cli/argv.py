"""Argv helpers for Fire-hostile repeatable flags (e.g. ``--env KEY=VALUE``)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Sequence

# Values peeled from argv before Fire sees them (Fire keeps only the last --env).
_APPLY_ENV_OVERRIDES: ContextVar[tuple[str, ...]] = ContextVar(
    "raft_apply_env_overrides",
    default=(),
)


def peel_repeatable_flag(
    argv: Sequence[str],
    flag: str,
) -> tuple[list[str], list[str]]:
    """Split ``argv`` into ``(values, remaining)`` for a repeatable long flag.

    Accepts ``--flag VALUE`` and ``--flag=VALUE``. Does not match longer
    flags that share a prefix (``--env`` will not peel ``--env-file``).
    """
    long = flag if flag.startswith("--") else f"--{flag}"
    values: list[str] = []
    remaining: list[str] = []
    i = 0
    n = len(argv)
    while i < n:
        arg = argv[i]
        if arg == long:
            if i + 1 >= n:
                remaining.append(arg)
                i += 1
                continue
            values.append(argv[i + 1])
            i += 2
            continue
        if arg.startswith(long + "="):
            values.append(arg[len(long) + 1 :])
            i += 1
            continue
        remaining.append(arg)
        i += 1
    return values, remaining


def set_apply_env_overrides(values: Sequence[str]):
    return _APPLY_ENV_OVERRIDES.set(tuple(values))


def get_apply_env_overrides() -> tuple[str, ...]:
    return _APPLY_ENV_OVERRIDES.get()


def reset_apply_env_overrides(token) -> None:
    _APPLY_ENV_OVERRIDES.reset(token)
