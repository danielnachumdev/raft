"""kind_id → RuleKind registry."""

from typing import Any, Dict, List

from raft.core.core.errors.cta import OperatorError, operator

from .rule_kind import RuleKind


class RuleKindRegistry:
    """Maps kind_id → rule kind."""

    def __init__(self) -> None:
        self._items: Dict[str, RuleKind] = {}

    def register(self, kind: RuleKind) -> None:
        if kind.kind_id in self._items:
            raise ValueError(f"duplicate rule kind '{kind.kind_id}'")
        self._items[kind.kind_id] = kind

    def get(self, kind_id: str) -> RuleKind:
        try:
            return self._items[kind_id]
        except KeyError:
            raise self._unknown(kind_id) from None

    def has(self, kind_id: str) -> bool:
        return kind_id in self._items

    def catalog(self) -> List[Dict[str, Any]]:
        return [item.catalog_entry() for item in self._items.values()]

    def _unknown(self, kind_id: str) -> OperatorError:
        known = ", ".join(self._items) if self._items else "(none)"
        return operator(
            f"unknown alert kind {kind_id!r} (known: {known}).",
            ["register a RuleKind for that kind_id"],
        )
