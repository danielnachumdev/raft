"""Type-id lookup for sync strategies (open for new source kinds)."""

from typing import Dict, List, Sequence

from ..errors.cta import OperatorError

from .strategy import SyncStrategy


class SourceSyncRegistry:
    """Maps ``spec.source`` → strategy. Unknown types raise OperatorError."""

    def __init__(self) -> None:
        self._items: Dict[str, SyncStrategy] = {}

    def register(self, strategy: SyncStrategy) -> None:
        type_id = strategy.type_id
        if type_id in self._items:
            raise ValueError(f"duplicate sync source '{type_id}'")
        self._items[type_id] = strategy

    def get(self, type_id: str) -> SyncStrategy:
        try:
            return self._items[type_id]
        except KeyError:
            raise self._unknown(type_id) from None

    def catalog(self) -> List[Dict[str, str]]:
        return [{"type_id": type_id} for type_id in self._items]

    def _unknown(self, type_id: str) -> OperatorError:
        known = self._known_list()
        return OperatorError(
            f"unknown app source {type_id!r} (known: {known}).\n"
            f"Fix: set spec.source to local, git, or docker"
        )

    def _known_list(self) -> str:
        ids: Sequence[str] = list(self._items)
        return ", ".join(ids) if ids else "(none)"
