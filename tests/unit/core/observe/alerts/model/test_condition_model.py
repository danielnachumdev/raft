"""Condition dataclasses."""
from raft.core.observe.alerts.model.condition import ConditionGroup, ConditionLeaf
from tests.unit.base import RaftTestCase

class TestConditionModel(RaftTestCase):
    def test_export(self) -> None:
        leaf = ConditionLeaf("s", {"target": "demo-api"}, "threshold", {"op": "gt"})
        assert leaf.to_export()["signal"] == "s"
        group = ConditionGroup("any", (leaf,))
        assert "any" in group.to_export()
