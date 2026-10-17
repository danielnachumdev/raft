"""Event count rule kind."""

from datetime import datetime, timedelta
from typing import Any, List, Mapping

from ..model.duration import AlertDuration
from ..model.issues import ValidationIssue
from ..signals.series import SubjectSeries, ValueType
from .catalog_entries import event_count_catalog
from .operators import Comparison
from .rule_kind import LeafResult, RuleKind


class EventCountKind(RuleKind):
    """Compare event count in a window to a threshold."""

    @property
    def kind_id(self) -> str:
        return "event_count"

    @property
    def value_types(self) -> frozenset:
        return frozenset({ValueType.EVENT})

    def catalog_entry(self) -> dict:
        return event_count_catalog(self.kind_id)

    def validate_params(
        self, params: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        op = params.get("op", "gte")
        if op not in Comparison.OPS:
            issues.append(ValidationIssue(f"{path}.op", f"unknown op {op!r}"))
        value = params.get("value")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            issues.append(ValidationIssue(f"{path}.value", "value must be int ≥ 0"))
        try:
            AlertDuration.parse(params.get("window"), path=f"{path}.window", default=3600)
        except Exception as exc:  # noqa: BLE001
            issues.append(ValidationIssue(f"{path}.window", str(exc).split("\n")[0]))
        return issues

    def window_seconds(self, params: Mapping[str, Any]) -> int:
        return AlertDuration.parse(params.get("window"), path="window", default=3600)

    def evaluate(
        self, series: SubjectSeries, params: Mapping[str, Any], *, now: datetime
    ) -> LeafResult:
        window = self.window_seconds(params)
        cutoff = now - timedelta(seconds=window)
        count = sum(1 for p in series.points if p.ts >= cutoff)
        op = str(params.get("op") or "gte")
        threshold = int(params["value"])
        matched = Comparison.apply(op, count, threshold)
        detail = f"count({AlertDuration.format(window)}) = {count} {op} {threshold}"
        return LeafResult(series.subject, matched, count, detail)
