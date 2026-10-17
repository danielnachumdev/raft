"""RuleKind ABC."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Mapping

from ..model.issues import ValidationIssue
from ..signals.series import SubjectSeries, ValueType


class LeafResult:
    """Result of evaluating one leaf against one subject series."""

    __slots__ = ("subject", "matched", "value", "detail")

    def __init__(
        self,
        subject: str,
        matched: Any,
        value: Any,
        detail: str,
    ) -> None:
        self.subject = subject
        self.matched = matched
        self.value = value
        self.detail = detail


class RuleKind(ABC):
    """Evaluate a leaf condition against a subject series."""

    @property
    @abstractmethod
    def kind_id(self) -> str: ...

    @property
    @abstractmethod
    def value_types(self) -> frozenset: ...

    def catalog_entry(self) -> Dict[str, Any]:
        return {
            "kind_id": self.kind_id,
            "label": self.kind_id,
            "value_types": [v.value for v in self.value_types],
            "fields": [],
        }

    @abstractmethod
    def validate_params(
        self, params: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]: ...

    @abstractmethod
    def window_seconds(self, params: Mapping[str, Any]) -> int: ...

    @abstractmethod
    def evaluate(
        self,
        series: SubjectSeries,
        params: Mapping[str, Any],
        *,
        now: datetime,
    ) -> LeafResult: ...
