"""Final coverage gaps D: engine reset/apply/prune branches."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.observe.alerts.engine.engine import AlertEngine
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.store.runtime_state import (
    AlertInstanceState,
    AlertRuntime,
)
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _rule() -> AlertRule:
    return AlertRule(
        id="demo-api-5xx-rate",
        name="demo",
        enabled=True,
        severity=NotificationSeverity.ERROR,
        description="",
        for_seconds=0,
        cooldown_seconds=0,
        repeat_every_seconds=0,
        notify_on_recovery=True,
        no_data="ok",
        channel_ids=(),
        condition=ConditionLeaf("metrics.http", {}, "threshold", {}),
    )


class TestFinalGapsD(RaftTestCase):
    def test_reset_and_apply_pop(self) -> None:
        engine = AlertEngine(Path(self.tmp_path))
        rule = _rule()
        prev = AlertInstanceState(
            rule_id=rule.id, subject="x", rule_hash="old", state="firing"
        )
        assert engine._maybe_reset_instance(prev, rule, "fp") is None
        runtime = AlertRuntime.empty()
        runtime.instances["fp"] = prev
        step = MagicMock(instance=None)
        engine._apply_transitions(
            runtime, [(rule, SubjectOutcome("x", True, ()), step, "fp", prev)], None
        )
        assert "fp" not in runtime.instances

    def test_notify_false_and_prune_orphan(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        engine = AlertEngine(home)
        step = MagicMock(notify=None, instance=None)
        assert (
            engine._notify_all(
                [(_rule(), SubjectOutcome("x", True, ()), step, "fp", None)],
                now=NOW,
            )
            == 0
        )
        runtime = AlertRuntime.empty()
        runtime.instances["demo-api-5xx-rate:x"] = AlertInstanceState(
            rule_id="demo-api-5xx-rate", subject="x", rule_hash="h", state="pending"
        )
        engine._prune(runtime, {"demo-api-5xx-rate": _rule()}, set())
        assert not runtime.instances

    def test_writable_already_logged(self) -> None:
        engine = AlertEngine(Path(self.tmp_path))
        with patch.object(engine._runtime, "ensure_writable", side_effect=OSError("ro")):
            engine._unwritable_logged = True
            assert engine._writable() is False
