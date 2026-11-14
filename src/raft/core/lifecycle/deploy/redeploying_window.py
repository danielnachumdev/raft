"""Mark intentional live cutover for status / edge maintenance pages."""

from pathlib import Path
from types import TracebackType
from typing import Optional, Type

from raft.core.core.models.state.redeploying_store import RedeployingStore


class RedeployingWindow:
    """Set ``deploy/redeploying`` for the cutover window; clear on exit."""

    def __init__(self, home: Path, app_name: str) -> None:
        self._store = RedeployingStore(home)
        self._name = app_name

    def __enter__(self) -> "RedeployingWindow":
        self._store.mark(self._name)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self._store.clear(self._name)
