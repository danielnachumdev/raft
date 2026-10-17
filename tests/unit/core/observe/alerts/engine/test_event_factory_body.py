"""AlertEventFactory body formatting."""
from datetime import datetime, timezone, timedelta
from raft.core.observe.alerts.engine.event_factory import AlertEventFactory
from raft.core.observe.alerts.engine.leaf_result import LeafValue, SubjectOutcome
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase

def _rule():
    return AlertRule(
        id="r", name="n", enabled=True, severity=NotificationSeverity.ERROR,
        description="desc", for_seconds=0, cooldown_seconds=0, repeat_every_seconds=0,
        notify_on_recovery=True, no_data="ok", channel_ids=(),
        condition=ConditionLeaf("metrics.http", {"target": "demo-api"}, "threshold", {}),
    )

class TestEventFactoryBody(RaftTestCase):
    def test_firing_body_and_duration(self) -> None:
        f = AlertEventFactory()
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        inst = AlertInstanceState("r", "demo-api", "h", "firing", firing_since=since, last_evaluated_at=since, last_values=[])
        leaf = LeafValue("p", "s", "d", 1, True, "detail", False)
        out = SubjectOutcome("demo-api", True, (leaf,))
        body = f._firing_body(_rule(), out, inst)
        assert "desc" in body and "detail" in body
        assert "m" in f._duration(since, since + timedelta(minutes=2))
        assert f._duration(None, since) == "unknown duration"
