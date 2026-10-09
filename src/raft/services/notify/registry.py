"""Type-id lookup for notification strategies (open for new classes)."""

from __future__ import annotations

from typing import Dict, List, Sequence

from raft.errors.cta import OperatorError, operator

from .strategy import NotificationStrategy


class NotificationRegistry:
    """Maps type_id → strategy. Unknown types raise OperatorError with Fix CTA."""

    def __init__(self) -> None:
        self._items: Dict[str, NotificationStrategy] = {}

    def register(self, strategy: NotificationStrategy) -> None:
        type_id = strategy.type_id
        if type_id in self._items:
            raise ValueError(f"duplicate notification type '{type_id}'")
        self._items[type_id] = strategy

    def get(self, type_id: str) -> NotificationStrategy:
        try:
            return self._items[type_id]
        except KeyError:
            raise self._unknown(type_id) from None

    def catalog(self) -> List[Dict[str, str]]:
        return [{"type_id": type_id} for type_id in self._items]

    def _unknown(self, type_id: str) -> OperatorError:
        known = self._known_list()
        return operator(
            f"unknown notification type {type_id!r} (known: {known}).",
            [
                "register a NotificationStrategy for that type_id, or",
                "fix the channel type to a catalog entry",
            ],
        )

    def _known_list(self) -> str:
        ids: Sequence[str] = list(self._items)
        return ", ".join(ids) if ids else "(none)"
