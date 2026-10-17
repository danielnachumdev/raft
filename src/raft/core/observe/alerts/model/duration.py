"""Parse and format alert duration strings."""

import re
from typing import Optional, Union

from raft.core.core.errors.cta import OperatorError

from ..constants import MAX_WINDOW_SECONDS

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_RE = re.compile(r"^(\d+)(s|m|h|d)$")


class AlertDuration:
    """Integer seconds or ``30s`` / ``5m`` / ``1h`` / ``7d`` strings."""

    @classmethod
    def parse(
        cls,
        raw: Union[int, float, str, None],
        *,
        path: str,
        default: Optional[int] = None,
        max_seconds: int = MAX_WINDOW_SECONDS,
        min_seconds: int = 0,
    ) -> int:
        if raw is None:
            if default is None:
                raise OperatorError(
                    f"{path}: duration is required.\nFix: use e.g. 5m or 300"
                )
            return default
        seconds = cls._to_seconds(raw, path=path)
        if seconds < min_seconds or seconds > max_seconds:
            raise OperatorError(
                f"{path}: duration {seconds}s out of range "
                f"[{min_seconds}, {max_seconds}].\n"
                f"Fix: choose a duration within the allowed bounds"
            )
        return seconds

    @classmethod
    def format(cls, seconds: int) -> str:
        if seconds % 86400 == 0 and seconds >= 86400:
            return f"{seconds // 86400}d"
        if seconds % 3600 == 0 and seconds >= 3600:
            return f"{seconds // 3600}h"
        if seconds % 60 == 0 and seconds >= 60:
            return f"{seconds // 60}m"
        return f"{seconds}s"

    @classmethod
    def _to_seconds(cls, raw: Union[int, float, str], *, path: str) -> int:
        if isinstance(raw, bool):
            raise OperatorError(f"{path}: duration must be int or string.\nFix: use 5m")
        if isinstance(raw, (int, float)):
            if int(raw) != raw or raw < 0:
                raise OperatorError(
                    f"{path}: duration must be a non-negative integer.\nFix: use 300"
                )
            return int(raw)
        if not isinstance(raw, str):
            raise OperatorError(f"{path}: duration must be int or string.\nFix: use 5m")
        match = _RE.match(raw.strip())
        if not match:
            raise OperatorError(
                f"{path}: invalid duration {raw!r}.\nFix: use 30s, 5m, 1h, or 7d"
            )
        amount, unit = match.groups()
        return int(amount) * _UNITS[unit]
