"""Condition tree nodes for alert rules."""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Union


@dataclass(frozen=True)
class ConditionLeaf:
    signal: str
    select: Mapping[str, Any]
    kind: str
    params: Mapping[str, Any]

    def to_export(self) -> Dict[str, Any]:
        return {
            "signal": self.signal,
            "select": dict(self.select),
            "kind": self.kind,
            "params": dict(self.params),
        }

    def to_public(self) -> Dict[str, Any]:
        return self.to_export()


@dataclass(frozen=True)
class ConditionGroup:
    op: str  # all | any
    children: tuple["ConditionNode", ...]

    def to_export(self) -> Dict[str, Any]:
        return {self.op: [c.to_export() for c in self.children]}

    def to_public(self) -> Dict[str, Any]:
        return self.to_export()


ConditionNode = Union[ConditionLeaf, ConditionGroup]
