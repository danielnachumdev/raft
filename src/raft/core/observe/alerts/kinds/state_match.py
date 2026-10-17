"""Latest-state membership rule kind."""

from datetime import datetime, timedelta
from typing import Any, List, Mapping

from ..model.issues import ValidationIssue
from ..signals.series import SubjectSeries, ValueType
from .catalog_entries import state_match_catalog
from .rule_kind import LeafResult, RuleKind


class StateMatchKind(RuleKind):
    """Match the latest state value against an allow/deny list."""

    @property
    def kind_id(self) -> str:
        return "state"

    @property
    def value_types(self) -> frozenset:
        return frozenset({ValueType.STATE})

    def catalog_entry(self) -> dict:
        return state_match_catalog(self.kind_id)

    def validate_params(
        self, params: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        match = params.get("match")
        if match not in ("in", "notIn"):
            issues.append(ValidationIssue(f"{path}.match", "match must be in or notIn"))
        values = params.get("values")
        if (
            not isinstance(values, list)
            or not values
            or len(values) > 10
            or any(not isinstance(v, str) for v in values)
        ):
            issues.append(
                ValidationIssue(f"{path}.values", "values must be 1–10 strings")
            )
        return issues

    def window_seconds(self, params: Mapping[str, Any]) -> int:
        return 600

    def evaluate(
        self, series: SubjectSeries, params: Mapping[str, Any], *, now: datetime
    ) -> LeafResult:
        cutoff = now - timedelta(seconds=self.window_seconds(params))
        points = [p for p in series.points if p.ts >= cutoff and p.value is not None]
        if not points:
            return LeafResult(series.subject, None, None, "no data")
        latest = str(points[-1].value)
        values = [str(v) for v in params["values"]]
        member = latest in values
        matched = member if params["match"] == "in" else not member
        detail = f"state={latest} {params['match']} {values}"
        return LeafResult(series.subject, matched, latest, detail)
