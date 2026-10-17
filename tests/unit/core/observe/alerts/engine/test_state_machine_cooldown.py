"""State machine cooldown and suppressed."""
from datetime import datetime, timezone, timedelta
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.engine.state_machine import AlertStateMachine
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase

def _rule(**kw):
    base = dict(
        id="r", name="n", enabled=True, severity=NotificationSeverity.WARNING,
        description="", for_seconds=0, cooldown_seconds=900, repeat_every_seconds=0,
        notify_on_recovery=True, no_data="ok", channel_ids=(),
        condition=ConditionLeaf("metrics.http", {"target": "demo-api"}, "threshold", {}),
    )
    base.update(kw)
    return AlertRule(**base)

class TestStateMachineCooldown(RaftTestCase):
    def test_cooldown_suppressed(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        m = AlertStateMachine()
        prev = AlertInstanceState(
            "r",
            "demo-api",
            "h",
            "pending",
            pending_since=now,
            cooldown_until=now + timedelta(hours=1),
            last_evaluated_at=now,
            last_values=[],
        )
        step = m.step(prev, SubjectOutcome("demo-api", True, ()), _rule(for_seconds=0), now=now)
        assert step.instance.suppressed
