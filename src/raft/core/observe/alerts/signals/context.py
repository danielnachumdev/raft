"""Per-tick memo shared by all signal sources."""

from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Sequence, TypeVar

T = TypeVar("T")


class SignalContext:
    """Per-tick read memo + facts shared by all sources in one evaluation."""

    def __init__(
        self, home: Path, now: datetime, *, app_names: Sequence[str]
    ) -> None:
        self._home = home
        self._now = now
        self._app_names = tuple(app_names)
        self._memo: Dict[str, object] = {}

    @property
    def now(self) -> datetime:
        return self._now

    @property
    def home(self) -> Path:
        return self._home

    @property
    def app_names(self) -> tuple:
        return self._app_names

    def memo(self, key: str, load: Callable[[], T]) -> T:
        if key not in self._memo:
            self._memo[key] = load()
        return self._memo[key]  # type: ignore[return-value]
