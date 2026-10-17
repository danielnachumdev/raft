"""RuleKind default catalog_entry."""
from datetime import datetime, timezone
from typing import Any, List, Mapping
from raft.core.observe.alerts.kinds.rule_kind import RuleKind, LeafResult
from raft.core.observe.alerts.model.issues import ValidationIssue
from raft.core.observe.alerts.signals.series import SubjectSeries, ValueType
from tests.unit.base import RaftTestCase

class _StubKind(RuleKind):
    @property
    def kind_id(self) -> str:
        return "stub"
    @property
    def value_types(self) -> frozenset:
        return frozenset({ValueType.NUMERIC})
    def validate_params(self, params: Mapping[str, Any], *, path: str) -> List[ValidationIssue]:
        return []
    def window_seconds(self, params: Mapping[str, Any]) -> int:
        return 60
    def evaluate(self, series: SubjectSeries, params: Mapping[str, Any], *, now: datetime) -> LeafResult:
        return LeafResult(series.subject, True, 1, "ok")

class TestRuleKindCatalog(RaftTestCase):
    def test_default_catalog(self) -> None:
        entry = _StubKind().catalog_entry()
        assert entry["value_types"] == ["numeric"]
