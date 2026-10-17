"""SignalSource ABC."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping

from .context import SignalContext
from .series import SubjectSeries, ValueType
from ..model.issues import ValidationIssue


class SignalSource(ABC):
    """Read/observe facts for alert evaluation."""

    @property
    @abstractmethod
    def type_id(self) -> str: ...

    @property
    @abstractmethod
    def value_type(self) -> ValueType: ...

    def catalog_entry(self) -> Dict[str, Any]:
        return {
            "type_id": self.type_id,
            "label": self.type_id,
            "value_type": self.value_type.value,
            "select_fields": [],
            "metrics": [],
        }

    @abstractmethod
    def validate_select(
        self, select: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]: ...

    @abstractmethod
    def query(
        self,
        select: Mapping[str, Any],
        *,
        window_seconds: int,
        ctx: SignalContext,
    ) -> List[SubjectSeries]: ...

    def describe(self, select: Mapping[str, Any]) -> str:
        return self.type_id
