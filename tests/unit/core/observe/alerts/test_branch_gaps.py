"""Branch coverage gaps for alerts."""
from pathlib import Path

from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.signals.control.container_status_source import ContainerStatusSource
from raft.core.observe.alerts.signals.control.graph_events_source import GraphEventsSource
from raft.core.observe.alerts.signals.context import SignalContext
from datetime import datetime, timezone
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestBranchGaps(RaftTestCase):
    def test_rule_parser_group_not_list(self) -> None:
        body = {**RULE, "condition": {"all": "not-a-list"}}
        assert not AlertRuleParser(AlertCatalogs.default()).validate(body).ok

    def test_rules_service_no_channel_check(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        svc = AlertRulesService(home)
        svc.create(RULE)
        svc.replace("demo-api-5xx-rate", RULE)

    def test_graph_action_filter(self) -> None:
        home = Path(self.tmp_path)
        store = GraphEventStore(home)
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        store.record_scaling(service="demo-api", app="demo-api", ts=now, metadata={"action": "wake"})
        ctx = SignalContext(home, now, app_names=["demo-api"])
        src = GraphEventsSource()
        match = src.query(
            {"target": "demo-api", "eventKind": "scaling", "action": "wake"},
            window_seconds=3600,
            ctx=ctx,
        )
        assert match[0].points
        miss = src.query(
            {"target": "demo-api", "eventKind": "scaling", "action": "idle"},
            window_seconds=3600,
            ctx=ctx,
        )
        assert miss[0].points == ()

    def test_container_invalid_target(self) -> None:
        issues = ContainerStatusSource().validate_select({"target": ""}, path="s")
        assert issues
