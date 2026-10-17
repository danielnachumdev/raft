"""AlertEventFactory."""
from datetime import datetime, timezone
from raft.core.observe.alerts.engine.event_factory import AlertEventFactory
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase

def _rule():
    return AlertRule(
        id="demo-api-5xx-rate", name="n", enabled=True, severity=NotificationSeverity.ERROR,
        description="", for_seconds=0, cooldown_seconds=60, repeat_every_seconds=0,
        notify_on_recovery=True, no_data="ok", channel_ids=(),
        condition=ConditionLeaf("metrics.http", {"target": "demo-api"}, "threshold", {}),
    )

class TestEventFactory(RaftTestCase):
    def test_firing_and_resolved(self) -> None:
        f = AlertEventFactory()
        inst = AlertInstanceState("demo-api-5xx-rate", "demo-api", "h", "firing", last_evaluated_at=datetime(2026,1,1,tzinfo=timezone.utc), last_values=[])
        out = SubjectOutcome("demo-api", True, ())
        ev = f.firing(_rule(), out, inst)
        assert ev.kind == "alert.firing"
        ev2 = f.resolved(_rule(), out, inst, now=datetime(2026,1,2,tzinfo=timezone.utc))
        assert ev2.kind == "alert.resolved"
