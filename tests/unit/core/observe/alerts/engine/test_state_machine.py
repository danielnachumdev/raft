"""AlertStateMachine transitions."""

from datetime import datetime, timezone, timedelta
from raft.core.observe.alerts.engine.fingerprint import AlertFingerprint
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.engine.state_machine import AlertStateMachine
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase


def _rule(**kwargs) -> AlertRule:
    base = dict(
        id="demo-api-5xx-rate",
        name="demo",
        enabled=True,
        severity=NotificationSeverity.ERROR,
        description="",
        for_seconds=0,
        cooldown_seconds=900,
        repeat_every_seconds=0,
        notify_on_recovery=True,
        no_data="ok",
        channel_ids=(),
        condition=ConditionLeaf("metrics.http", {"target": "demo-api"}, "threshold", {}),
    )
    base.update(kwargs)
    return AlertRule(**base)


class TestAlertStateMachine(RaftTestCase):
    def test_fire_immediate(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        outcome = SubjectOutcome("demo-api", True, ())
        step = AlertStateMachine().step(None, outcome, _rule(), now=now)
        assert step.notify == "firing"
        assert step.instance is not None
        assert step.instance.state == "firing"

    def test_pending_then_fire(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        rule = _rule(for_seconds=120)
        outcome = SubjectOutcome("demo-api", True, ())
        machine = AlertStateMachine()
        first = machine.step(None, outcome, rule, now=now)
        assert first.notify is None
        assert first.instance.state == "pending"
        later = now + timedelta(seconds=120)
        second = machine.step(first.instance, outcome, rule, now=later)
        assert second.notify == "firing"

    def test_resolve_with_recovery(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        machine = AlertStateMachine()
        fired = machine.step(
            None, SubjectOutcome("demo-api", True, ()), _rule(), now=now
        )
        resolved = machine.step(
            fired.instance,
            SubjectOutcome("demo-api", False, ()),
            _rule(),
            now=now + timedelta(seconds=10),
        )
        assert resolved.notify == "resolved"
