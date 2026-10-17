"""Extra AlertStateMachine branches."""

from datetime import datetime, timezone, timedelta
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.engine.state_machine import AlertStateMachine
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase


def _rule(**kw) -> AlertRule:
    base = dict(
        id="demo-api-5xx-rate",
        name="demo",
        enabled=True,
        severity=NotificationSeverity.ERROR,
        description="",
        for_seconds=0,
        cooldown_seconds=900,
        repeat_every_seconds=300,
        notify_on_recovery=False,
        no_data="keep",
        channel_ids=(),
        condition=ConditionLeaf("metrics.http", {"target": "demo-api"}, "threshold", {}),
    )
    base.update(kw)
    return AlertRule(**base)


class TestStateMachineExtra(RaftTestCase):
    def test_no_data_keep_and_repeat(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        m = AlertStateMachine()
        kept = m.step(None, SubjectOutcome("demo-api", None, ()), _rule(), now=now)
        assert kept.instance is None
        fired = m.step(None, SubjectOutcome("demo-api", True, ()), _rule(for_seconds=60), now=now)
        later = m.step(fired.instance, SubjectOutcome("demo-api", True, ()), _rule(for_seconds=60, repeat_every_seconds=60), now=now + timedelta(minutes=5))
        assert later.notify == "firing"
