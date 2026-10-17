"""Rule kind value_types properties + base catalog."""

from raft.core.observe.alerts.kinds.event_count import EventCountKind
from raft.core.observe.alerts.kinds.rule_kind import RuleKind
from raft.core.observe.alerts.kinds.state_match import StateMatchKind
from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from raft.core.observe.alerts.signals.series import ValueType
from tests.unit.base import RaftTestCase


class Tiny(RuleKind):
    @property
    def kind_id(self):
        return "tiny"

    @property
    def value_types(self):
        return frozenset({ValueType.NUMERIC})

    def validate_params(self, params, *, path):
        return []

    def window_seconds(self, params):
        return 1

    def evaluate(self, series, params, *, now):
        from raft.core.observe.alerts.kinds.rule_kind import LeafResult

        return LeafResult("x", True, 1, "d")


class TestValueTypesProps(RaftTestCase):
    def test_props(self) -> None:
        assert ValueType.NUMERIC in ThresholdKind().value_types
        assert ValueType.EVENT in EventCountKind().value_types
        assert ValueType.STATE in StateMatchKind().value_types
        assert Tiny().catalog_entry()["kind_id"] == "tiny"
        assert ThresholdKind()._sym("nope") == "nope"
