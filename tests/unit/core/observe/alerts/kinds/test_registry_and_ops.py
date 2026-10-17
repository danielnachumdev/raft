"""Registries and aggregate/op edge cases."""

import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.kinds.aggregates import Aggregates
from raft.core.observe.alerts.kinds.kind_registry import RuleKindRegistry
from raft.core.observe.alerts.kinds.operators import Comparison
from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from raft.core.observe.alerts.kinds.rule_kind import RuleKind
from tests.unit.base import RaftTestCase


class TestRegistryAndOps(RaftTestCase):
    def test_unknown_aggregate_and_op(self) -> None:
        with pytest.raises(ValueError):
            Aggregates.apply("nope", [1.0])
        with pytest.raises(ValueError):
            Comparison.apply("nope", 1, 2)

    def test_kind_registry(self) -> None:
        reg = RuleKindRegistry()
        reg.register(ThresholdKind())
        with pytest.raises(ValueError):
            reg.register(ThresholdKind())
        assert reg.get("threshold").kind_id == "threshold"
        with pytest.raises(OperatorError):
            reg.get("missing")
