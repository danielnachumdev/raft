"""Leaf and subject evaluation outcomes."""

from dataclasses import dataclass
from typing import Any, Optional, Tuple


@dataclass(frozen=True)
class LeafValue:
    path: str
    signal: str
    describe: str
    value: Any
    matched: Optional[bool]
    detail: str
    no_data: bool

    def to_public(self) -> dict:
        return {
            "path": self.path,
            "signal": self.signal,
            "describe": self.describe,
            "metric": self.describe,
            "value": self.value,
            "matched": self.matched,
            "detail": self.detail,
            "noData": self.no_data,
        }


@dataclass(frozen=True)
class SubjectOutcome:
    subject: str
    matched: Optional[bool]
    leaves: Tuple[LeafValue, ...]
