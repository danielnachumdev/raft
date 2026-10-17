"""ConditionEvaluator all/any and no-data."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.engine.condition_evaluator import ConditionEvaluator
from raft.core.observe.alerts.model.condition import ConditionGroup, ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.notify.severity import NotificationSeverity
from raft.core.observe.alerts.signals.context import SignalContext
from tests.unit.base import RaftTestCase


def _rule(condition) -> AlertRule:
    return AlertRule(
        id="r1",
        name="r",
        enabled=True,
        severity=NotificationSeverity.WARNING,
        description="",
        for_seconds=0,
        cooldown_seconds=0,
        repeat_every_seconds=0,
        notify_on_recovery=True,
        no_data="alerting",
        channel_ids=(),
        condition=condition,
    )


class TestConditionEvaluator(RaftTestCase):
    def test_all_and_wildcard(self) -> None:
        home = Path(self.tmp_path)
        ctx = SignalContext(home, datetime(2026, 10, 17, tzinfo=timezone.utc), app_names=["demo-api"])
        leaf = ConditionLeaf(
            "metrics.http",
            {"target": "*", "metric": "requests"},
            "threshold",
            {"aggregate": "avg", "window": "5m", "op": "gt", "value": 0},
        )
        group = ConditionGroup("all", (leaf,))
        ev = ConditionEvaluator(AlertCatalogs.default())
        out = ev.evaluate(_rule(group), ctx)
        assert out

    def test_no_data_leaf(self) -> None:
        home = Path(self.tmp_path)
        ctx = SignalContext(home, datetime(2026, 10, 17, tzinfo=timezone.utc), app_names=[])
        leaf = ConditionLeaf(
            "metrics.http",
            {"target": "missing", "metric": "requests"},
            "threshold",
            {"aggregate": "avg", "window": "5m", "op": "gt", "value": 999},
        )
        ev = ConditionEvaluator(AlertCatalogs.default())
        out = ev.evaluate(_rule(leaf), ctx)
        assert out[0].matched is True
