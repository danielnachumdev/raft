"""AlertRuntime mapping roundtrip."""
from datetime import datetime, timezone
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState, AlertRuntime
from tests.unit.base import RaftTestCase

class TestRuntimeState(RaftTestCase):
    def test_instance_mapping(self) -> None:
        inst = AlertInstanceState(
            "r", "demo-api", "h", "firing",
            firing_since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_values=[{"x": 1}],
        )
        back = AlertInstanceState.from_mapping(inst.to_mapping())
        assert back.rule_id == "r"
        rt = AlertRuntime(instances={"a": inst})
        pub = rt.to_mapping()
        assert AlertRuntime.from_mapping(pub).instances["a"].subject == "demo-api"
