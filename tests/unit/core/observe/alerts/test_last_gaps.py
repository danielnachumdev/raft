"""Remaining alert coverage gaps (small tests)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.constants import MAX_RULES
from raft.core.observe.alerts.engine.leaf_result import SubjectOutcome
from raft.core.observe.alerts.engine.state_machine import AlertStateMachine
from raft.core.observe.alerts.model.condition import ConditionLeaf
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.model.issues import ValidationIssue, ValidationReport
from raft.core.observe.alerts.model.rule import AlertRule
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.service.status_view import AlertStatusView
from raft.core.observe.alerts.signals.control.container_status_source import (
    ContainerStatusSource,
)
from raft.core.observe.alerts.signals.control.graph_events_source import (
    GraphEventsSource,
)
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from raft.core.observe.notify.severity import NotificationSeverity
from raft.services.cli.commands.alerts import AlertsCLI
from raft.services.serve.alerts import ServeAlertsApi
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def _rule(**kw) -> AlertRule:
    base = dict(
        id="r",
        name="n",
        enabled=True,
        severity=NotificationSeverity.WARNING,
        description="",
        for_seconds=0,
        cooldown_seconds=0,
        repeat_every_seconds=60,
        notify_on_recovery=True,
        no_data="ok",
        channel_ids=(),
        condition=ConditionLeaf("metrics.http", {}, "threshold", {}),
    )
    base.update(kw)
    return AlertRule(**base)


class TestLastGaps(RaftTestCase):
    def test_document_max_rules(self) -> None:
        regs = AlertCatalogs.default()
        rules = [{**RULE, "id": f"rule-{i}"} for i in range(MAX_RULES + 1)]
        with pytest.raises(OperatorError):
            AlertRulesDocument.from_mapping(
                {"version": 1, "rules": rules}, registries=regs
            )

    def test_state_machine_no_repeat_yet(self) -> None:
        rule = _rule(repeat_every_seconds=300)
        m = AlertStateMachine()
        fired = m.step(None, SubjectOutcome("demo-api", True, ()), rule, now=NOW)
        hold = m.step(
            fired.instance,
            SubjectOutcome("demo-api", True, ()),
            rule,
            now=NOW + timedelta(seconds=30),
        )
        assert hold.notify is None

    def test_state_machine_repeat(self) -> None:
        rule = _rule()
        m = AlertStateMachine()
        fired = m.step(None, SubjectOutcome("demo-api", True, ()), rule, now=NOW)
        again = m.step(
            fired.instance,
            SubjectOutcome("demo-api", True, ()),
            rule,
            now=NOW + timedelta(minutes=2),
        )
        assert again.notify == "firing"

    def test_status_skip_ok_instance(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "alerts: {enabled: true, intervalSeconds: 60}\n"
            "notifications: {enabled: true, channels: []}\n",
            encoding="utf-8",
        )
        AlertRulesService(home).create(RULE)
        rt = AlertRuntimeStore(home).load()
        rt.instances["ok"] = AlertInstanceState(
            "demo-api-5xx-rate", "demo-api", "h", "ok"
        )
        AlertRuntimeStore(home).save(rt)
        rows = AlertStatusView(home).build()["instances"]
        assert all(r["state"] != "ok" for r in rows)

    def test_graph_describe(self) -> None:
        src = GraphEventsSource()
        assert src.describe({"target": "demo-api", "eventKind": "stop"}) == (
            "demo-api stop"
        )
        assert GraphEventsSource._parse_ts("bad") is None

    def test_container_validate_ok_and_series(self) -> None:
        cs = ContainerStatusSource()
        assert cs.validate_select({"target": "demo-api"}, path="p") == []
        series = cs._series(
            "demo-api", [{"ts": 1}, {"ts": "2024-01-01T00:00:00+00:00"}], wildcard=False
        )
        assert series.subject == "demo-api"

    def test_rule_parser_leaves_and_warning(self) -> None:
        p = AlertRuleParser(AlertCatalogs.default())
        rep = ValidationReport()
        p._validate_leaves("x", "p", rep)
        assert not rep.errors
        rep2 = ValidationReport()
        p._merge_issues([ValidationIssue("w", "m", level="warning")], rep2)
        assert rep2.warnings

    def test_cli_summarize_leaf(self) -> None:
        home = Path(self.tmp_path)
        cli = AlertsCLI(Stack(root=home, apps=()))
        assert cli._summarize({"signal": "metrics.http", "kind": "threshold"}) == (
            "metrics.http threshold"
        )

    def test_api_delete_and_test_missing(self) -> None:
        home = Path(self.tmp_path)
        api = ServeAlertsApi(Stack(root=home, apps=[]))
        app = FastAPI()
        api.register(app)
        client = TestClient(app)
        with patch.object(api._service, "delete", side_effect=OperatorError("bad\nFix")):
            assert client.delete("/api/alerts/rules/x").status_code == 400
        assert client.post("/api/alerts/rules/x/test").status_code == 404
