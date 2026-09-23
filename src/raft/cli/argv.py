"""Argv helpers for Fire-hostile repeatable flags (e.g. ``--env KEY=VALUE``)."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional, Sequence

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
    long = _normalize_long_flag(flag)
    values: list[str] = []
    remaining: list[str] = []
    i = 0
    n = len(argv)
    while i < n:
        peeled = _try_peel_at(argv, i, long)
        if peeled is None:
            remaining.append(argv[i])
            i += 1
            continue
        value, next_i = peeled
        if value is None:
            # Lone ``--flag`` with no following value — leave it for Fire.
            remaining.append(argv[i])
            i = next_i
            continue
        values.append(value)
        i = next_i
    return values, remaining


def set_apply_env_overrides(values: Sequence[str]):
    return _APPLY_ENV_OVERRIDES.set(tuple(values))


def get_apply_env_overrides() -> tuple[str, ...]:
    return _APPLY_ENV_OVERRIDES.get()


def reset_apply_env_overrides(token) -> None:
    _APPLY_ENV_OVERRIDES.reset(token)


def _normalize_long_flag(flag: str) -> str:
    return flag if flag.startswith("--") else f"--{flag}"


def _try_peel_at(
    argv: Sequence[str],
    i: int,
    long: str,
) -> Optional[tuple[Optional[str], int]]:
    """If ``argv[i]`` is ``long`` (or ``long=…``), return ``(value_or_None, next_i)``.

    ``value`` is ``None`` when the flag is present but has no following token
    (caller should leave the bare flag in ``remaining``).
    """
    arg = argv[i]
    if arg == long:
        if i + 1 >= len(argv):
            return None, i + 1
        return argv[i + 1], i + 2
    equals_value = _equals_flag_value(arg, long)
    if equals_value is not None:
        return equals_value, i + 1
    return None


def _equals_flag_value(arg: str, long: str) -> Optional[str]:
    prefix = long + "="
    if arg.startswith(prefix):
        return arg[len(prefix) :]
    return None
