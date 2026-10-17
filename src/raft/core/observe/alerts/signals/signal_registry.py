"""type_id → SignalSource registry."""

from typing import Any, Dict, List, Sequence

from raft.core.core.errors.cta import OperatorError, operator

from .signal_source import SignalSource


class SignalRegistry:
    """Maps type_id → signal source."""

    def __init__(self) -> None:
        self._items: Dict[str, SignalSource] = {}

    def register(self, source: SignalSource) -> None:
        if source.type_id in self._items:
            raise ValueError(f"duplicate signal type '{source.type_id}'")
        self._items[source.type_id] = source

    def get(self, type_id: str) -> SignalSource:
        try:
            return self._items[type_id]
        except KeyError:
            raise self._unknown(type_id) from None

    def has(self, type_id: str) -> bool:
        return type_id in self._items

    def catalog(self) -> List[Dict[str, Any]]:
        return [item.catalog_entry() for item in self._items.values()]

    def _unknown(self, type_id: str) -> OperatorError:
        known = ", ".join(self._items) if self._items else "(none)"
        return operator(
            f"unknown alert signal {type_id!r} (known: {known}).",
            ["register a SignalSource for that type_id"],
        )
