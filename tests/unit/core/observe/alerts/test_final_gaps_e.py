"""Final coverage gaps E: state machine + event duration + parser edges."""

from datetime import datetime, timedelta, timezone

from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.constants import MAX_LEAVES, MAX_RULES
from raft.core.observe.alerts.engine.event_factory import AlertEventFactory
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.engine.state_machine import AlertStateMachine
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.condition_parser import ConditionParser
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.model.issues import ValidationIssue, ValidationReport
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.notify.severity import NotificationSeverity
from raft.core.core.errors.cta import OperatorError
from tests.unit.base import RaftTestCase
import pytest

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _rule(**kw) -> AlertRule:
    base = dict(
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
    base.update(kw)
    return AlertRule(**base)


class TestFinalGapsE(RaftTestCase):
    def test_still_firing_repeat(self) -> None:
        sm = AlertStateMachine()
        rule = _rule(repeat_every_seconds=60)
        prev = AlertInstanceState(
            rule_id=rule.id,
            subject="x",
            rule_hash="h",
            state="firing",
            last_notified_at=NOW,
        )
        later = NOW + timedelta(seconds=120)
        step = sm.step(prev, SubjectOutcome("x", True, ()), rule, now=later)
        assert step.notify == "firing"

    def test_pending_clears_on_false(self) -> None:
        sm = AlertStateMachine()
        rule = _rule(for_seconds=60)
        prev = AlertInstanceState(
            rule_id=rule.id,
            subject="x",
            rule_hash="h",
            state="pending",
            pending_since=NOW,
        )
        step = sm.step(prev, SubjectOutcome("x", False, ()), rule, now=NOW)
        assert step.instance is None or step.instance.state == "ok"

    def test_duration_seconds(self) -> None:
        assert AlertEventFactory._duration(NOW, NOW + timedelta(seconds=5)) == "5s"
        assert AlertEventFactory._duration(None, NOW) == "unknown duration"

    def test_condition_parser_edges(self) -> None:
        report = ValidationReport()
        leaves: list = [0]
        parser = ConditionParser()
        parser._parse("bad", "c", depth=0, report=report, leaf_count=leaves)
        assert report.errors
        report2 = ValidationReport()
        parser._valid_children(list(range(9)), "c", "all", report2)
        assert any("at most 8" in i.message for i in report2.errors)
        report3 = ValidationReport()
        leaves3 = [MAX_LEAVES]
        parser._leaf({}, "c", report=report3, leaf_count=leaves3)
        assert any("leaves" in i.message for i in report3.errors)

    def test_document_max_and_merge_warn(self) -> None:
        with pytest.raises(OperatorError):
            AlertRulesDocument._validate_header(
                {"version": 1, "rules": [{}] * (MAX_RULES + 1)}, "doc"
            )
        report = ValidationReport()
        AlertRuleParser._merge_issues(
            [ValidationIssue("p", "w", "warning")], report
        )
        assert report.warnings
        AlertRuleParser(AlertCatalogs.default())._validate_leaves(
            "not-map", "c", report
        )
