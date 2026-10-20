"""Final coverage gaps B: engine prune/notify/writable."""

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


class TestFinalGapsB(RaftTestCase):
    def test_prune(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        engine = AlertEngine(home)
        runtime = AlertRuntime.empty()
        runtime.instances["gone:x"] = AlertInstanceState(
            rule_id="gone", subject="x", rule_hash="h", state="firing"
        )
        engine._prune(runtime, {"demo-api-5xx-rate": _rule()}, set())
        assert "gone:x" not in runtime.instances

    def test_notify_skip_and_writable(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        engine = AlertEngine(home)
        step = MagicMock(notify="firing", instance=None)
        assert (
            engine._notify_all(
                [(_rule(), SubjectOutcome("x", True, ()), step, "fp", None)],
                now=NOW,
            )
            == 0
        )
        with patch.object(engine._runtime, "ensure_writable", side_effect=OSError("ro")):
            engine._unwritable_logged = False
            assert engine._writable() is False

    def test_load_apps_error(self) -> None:
        engine = AlertEngine(Path(self.tmp_path))
        with patch(
            "raft.core.observe.alerts.engine.engine.Stack.load_apps",
            side_effect=RuntimeError("x"),
        ):
            assert engine._load_apps() == []
