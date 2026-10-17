"""Numeric threshold rule kind."""

from datetime import datetime, timedelta
from typing import Any, List, Mapping

from ..model.duration import AlertDuration
from ..model.issues import ValidationIssue
from ..signals.series import SubjectSeries, ValueType
from .aggregates import Aggregates
from .catalog_entries import threshold_catalog
from .operators import Comparison
from .rule_kind import LeafResult, RuleKind


class ThresholdKind(RuleKind):
    """Compare an aggregate over a window to a threshold."""

    @property
    def kind_id(self) -> str:
        return "threshold"

    @property
    def value_types(self) -> frozenset:
        return frozenset({ValueType.NUMERIC})

    def catalog_entry(self) -> dict:
        return threshold_catalog(self.kind_id)

    def validate_params(
        self, params: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        agg = params.get("aggregate", "avg")
        if agg not in Aggregates.NAMES:
            issues.append(ValidationIssue(f"{path}.aggregate", f"unknown aggregate {agg!r}"))
        op = params.get("op", "gt")
        if op not in Comparison.OPS:
            issues.append(ValidationIssue(f"{path}.op", f"unknown op {op!r}"))
        if "value" not in params or not isinstance(params["value"], (int, float)):
            issues.append(ValidationIssue(f"{path}.value", "value must be a number"))
        try:
            AlertDuration.parse(params.get("window"), path=f"{path}.window", default=300)
        except Exception as exc:  # noqa: BLE001
            issues.append(ValidationIssue(f"{path}.window", str(exc).split("\n")[0]))
        return issues

    def window_seconds(self, params: Mapping[str, Any]) -> int:
        return AlertDuration.parse(params.get("window"), path="window", default=300)

    def evaluate(
        self, series: SubjectSeries, params: Mapping[str, Any], *, now: datetime
    ) -> LeafResult:
        window = self.window_seconds(params)
        cutoff = now - timedelta(seconds=window)
        values = [
            float(p.value)
            for p in series.points
            if p.value is not None and p.ts >= cutoff
        ]
        agg_name = str(params.get("aggregate") or "avg")
        op = str(params.get("op") or "gt")
        threshold = float(params["value"])
        aggregated = Aggregates.apply(agg_name, values)
        if aggregated is None:
            return LeafResult(series.subject, None, None, "no data")
        matched = Comparison.apply(op, aggregated, threshold)
        detail = (
            f"{agg_name}({AlertDuration.format(window)}) = {aggregated:g} "
            f"{self._sym(op)} {threshold:g}"
        )
        return LeafResult(series.subject, matched, aggregated, detail)

    @staticmethod
    def _sym(op: str) -> str:
        return {
            "gt": ">",
            "gte": "≥",
            "lt": "<",
            "lte": "≤",
            "eq": "=",
            "ne": "≠",
        }.get(op, op)
