"""AlertRuleEvaluator error mapping."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.engine.condition_evaluator import ConditionEvaluator
from raft.core.observe.alerts.engine.rule_evaluator import AlertRuleEvaluator
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.notify.severity import NotificationSeverity
from tests.unit.base import RaftTestCase


def _rule() -> AlertRule:
    return AlertRule(
        id="r",
        name="r",
        enabled=True,
        severity=NotificationSeverity.WARNING,
        description="",
        for_seconds=0,
        cooldown_seconds=0,
        repeat_every_seconds=0,
        notify_on_recovery=True,
        no_data="ok",
        channel_ids=(),
        condition=ConditionLeaf(
            "metrics.http",
            {"target": "demo-api", "metric": "requests"},
            "threshold",
            {},
        ),
    )


class TestRuleEvaluator(RaftTestCase):
    def test_operator_and_os_errors(self) -> None:
        ev = AlertRuleEvaluator(AlertCatalogs.default())
        ctx = SignalContext(
            Path(self.tmp_path),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            app_names=[],
        )
        with patch.object(
            ConditionEvaluator, "evaluate", side_effect=OperatorError("bad\nFix")
        ):
            err, out = ev.evaluate(_rule(), ctx)
        assert err == "bad" and out == []
        with patch.object(ConditionEvaluator, "evaluate", side_effect=OSError("disk")):
            err2, _ = ev.evaluate(_rule(), ctx)
        assert err2.startswith("OSError")
