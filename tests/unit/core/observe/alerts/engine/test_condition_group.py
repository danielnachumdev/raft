"""ConditionEvaluator any group."""
from datetime import datetime, timezone
from pathlib import Path
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.engine.condition_evaluator import ConditionEvaluator
from raft.core.observe.alerts.model.condition import ConditionGroup, ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase

def _rule(cond):
    return AlertRule(
        id="r", name="n", enabled=True, severity=NotificationSeverity.WARNING,
        description="", for_seconds=0, cooldown_seconds=0, repeat_every_seconds=0,
        notify_on_recovery=True, no_data="keep", channel_ids=(), condition=cond,
    )

class TestConditionGroup(RaftTestCase):
    def test_any_composition(self) -> None:
        home = Path(self.tmp_path)
        ctx = SignalContext(home, datetime(2026, 1, 1, tzinfo=timezone.utc), app_names=[])
        leaves = (
            ConditionLeaf("metrics.http", {"target": "edge", "metric": "requests"}, "threshold", {"aggregate": "avg", "window": "5m", "op": "gt", "value": 999}),
            ConditionLeaf("metrics.http", {"target": "demo-api", "metric": "requests"}, "threshold", {"aggregate": "avg", "window": "5m", "op": "gt", "value": 999}),
        )
        out = ConditionEvaluator(AlertCatalogs.default()).evaluate(_rule(ConditionGroup("any", leaves)), ctx)
        assert out
