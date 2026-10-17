"""State machine repeat / cooldown / keep branches."""

from datetime import datetime, timedelta, timezone
from dataclasses import replace

from raft.core.observe.alerts.engine.leaf_result import LeafValue, SubjectOutcome
from raft.core.observe.alerts.engine.state_machine import AlertStateMachine
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase

NOW = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)


def _rule(**kw) -> AlertRule:
    base = dict(
        id="demo-api-5xx-rate",
        name="demo",
        enabled=True,
        severity=NotificationSeverity.ERROR,
        description="",
        for_seconds=0,
        cooldown_seconds=60,
        repeat_every_seconds=300,
        notify_on_recovery=True,
        no_data="ok",
        channel_ids=(),
        condition=ConditionLeaf("metrics.http", {}, "threshold", {}),
    )
    base.update(kw)
    return AlertRule(**base)


def _inst(**kw) -> AlertInstanceState:
    base = dict(
        rule_id="demo-api-5xx-rate",
        subject="demo-api",
        rule_hash="h",
        state="ok",
        last_evaluated_at=NOW,
        last_values=[],
    )
    base.update(kw)
    return AlertInstanceState(**base)


class TestStateMachineMore(RaftTestCase):
    def test_keep_and_repeat(self) -> None:
        sm = AlertStateMachine()
        outcome = SubjectOutcome("demo-api", None, ())
        assert sm.step(None, outcome, _rule(), now=NOW).instance is None
        prev = _inst(state="pending", pending_since=NOW)
        assert sm.step(prev, outcome, _rule(), now=NOW).instance is not None
        firing = _inst(state="firing", firing_since=NOW, last_notified_at=NOW)
        true = SubjectOutcome("demo-api", True, ())
        rep = sm._still_firing(firing, true, _rule(), now=NOW + timedelta(seconds=400))
        assert rep.notify == "firing"
        assert not sm._should_repeat(
            replace(firing, suppressed=True), _rule(), now=NOW + timedelta(hours=1)
        )
        assert not sm._should_repeat(
            replace(firing, last_notified_at=None), _rule(), now=NOW
        )

    def test_cooldown_and_resolve(self) -> None:
        sm = AlertStateMachine()
        cool = _inst(state="ok", cooldown_until=NOW + timedelta(seconds=30))
        assert sm._keep_cooldown(cool, NOW) is not None
        assert sm._keep_cooldown(cool, NOW + timedelta(seconds=60)) is None
        firing = _inst(state="firing", firing_since=NOW)
        true = SubjectOutcome("demo-api", True, ())
        assert (
            sm._resolve_holder(firing, true, _rule(cooldown_seconds=0), now=NOW) is None
        )
        pending = _inst(state="pending", pending_since=NOW)
        hold = sm._pending_hold(
            pending, true, _rule(for_seconds=60), now=NOW + timedelta(seconds=10)
        )
        assert hold.notify is None
