"""Branch coverage gaps for alerts."""

from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.models.state.graph_event import GraphEvent
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.issues import ValidationReport
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.signals.control.container_status_source import (
    ContainerStatusSource,
)
from raft.core.observe.alerts.signals.control.graph_events_source import (
    GraphEventsSource,
)
from raft.core.observe.alerts.signals.context import SignalContext
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

_SETTINGS = (
    "notifications:\n"
    "  enabled: true\n"
    "  channels:\n"
    "    - id: ops\n"
    "      type: webhook\n"
    "      settings:\n"
    "        url: https://hooks.example.invalid/raft\n"
)


class TestBranchGaps(RaftTestCase):
    def test_rule_parser_group_not_list(self) -> None:
        body = {**RULE, "condition": {"all": "not-a-list"}}
        assert not AlertRuleParser(AlertCatalogs.default()).validate(body).ok

    def test_validate_leaves_non_list_children(self) -> None:
        report = ValidationReport()
        AlertRuleParser(AlertCatalogs.default())._validate_leaves(
            {"all": "x"}, "c", report
        )

    def test_validate_leaf_skips_bad_select_params(self) -> None:
        report = ValidationReport()
        AlertRuleParser(AlertCatalogs.default())._validate_leaf(
            {
                "signal": "metrics.http",
                "kind": "threshold",
                "select": "x",
                "params": ["y"],
            },
            "c",
            report,
        )

    def test_rules_service_no_channel_check(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        svc = AlertRulesService(home)
        svc.create(RULE)
        svc.replace("demo-api-5xx-rate", RULE)

    def test_known_channel_ids_accepted(self) -> None:
        home = self._alerts_home()
        self._write_settings(home)
        AlertRulesService(home).create({**RULE, "channelIds": ["ops"]})

    def test_channel_warnings_skip_non_mapping(self) -> None:
        report = ValidationReport()
        AlertRulesService(Path(self.tmp_path))._channel_warnings(
            {"rules": ["x", {**RULE, "channelIds": ["ops"]}]}, report
        )
        assert not report.warnings

    def test_graph_action_filter(self) -> None:
        home = Path(self.tmp_path)
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        GraphEventStore(home).record_scaling(
            service="demo-api", app="demo-api", action="wake", ts=now
        )
        self._assert_action_filter(home, now)

    def test_graph_skips_unparseable_ts(self) -> None:
        src = GraphEventsSource()
        bad = GraphEvent(kind="scaling", ts="not-a-date", service="demo-api")
        assert src._wildcard([bad], "scaling") == []
        assert src._points([bad], "scaling") == []

    def test_container_invalid_target(self) -> None:
        issues = ContainerStatusSource().validate_select({"target": ""}, path="s")
        assert issues

    def _alerts_home(self) -> Path:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        return home

    def _write_settings(self, home: Path) -> None:
        (home / "host" / "settings.yaml").write_text(_SETTINGS, encoding="utf-8")

    def _assert_action_filter(self, home: Path, now: datetime) -> None:
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
