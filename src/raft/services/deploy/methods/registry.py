"""Type-id lookup for deployment methods (open for new classes)."""

from __future__ import annotations

from typing import Dict, List, Sequence

from raft.errors.cta import OperatorError, operator

from .method import DeploymentMethod


class DeploymentMethodRegistry:
    """Maps type_id → strategy. Unknown types raise OperatorError with Fix CTA."""

    def __init__(self) -> None:
        self._items: Dict[str, DeploymentMethod] = {}

    def register(self, strategy: DeploymentMethod) -> None:
        type_id = strategy.type_id
        if type_id in self._items:
            raise ValueError(f"duplicate deployment method '{type_id}'")
        self._items[type_id] = strategy

    def get(self, type_id: str) -> DeploymentMethod:
        try:
            return self._items[type_id]
        except KeyError:
            raise self._unknown(type_id) from None

    def catalog(self) -> List[Dict[str, str]]:
        return [{"type_id": type_id} for type_id in self._items]

    def _unknown(self, type_id: str) -> OperatorError:
        known = self._known_list()
        return operator(
            f"unknown deployment method {type_id!r} (known: {known}).",
            [
                "register a DeploymentMethod for that type_id, or",
                "set spec.deployment.method to a catalog entry (seamless, inplace)",
            ],
        )

    def _known_list(self) -> str:
        ids: Sequence[str] = list(self._items)
        return ", ".join(ids) if ids else "(none)"
