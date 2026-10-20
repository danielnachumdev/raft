"""AlertEngine error and edge paths."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.engine.engine import AlertEngine
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertEngineEdges(RaftTestCase):
    def _home(self) -> Path:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        return home

    def test_document_error_persisted(self) -> None:
        home = self._home()
        engine = AlertEngine(home, registries=AlertCatalogs.default())
        with patch.object(engine._rules, "load", side_effect=OperatorError("bad\nFix")):
            report = engine.tick(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert report.document_error == "bad"
        runtime = AlertRuntimeStore(home).load()
        assert runtime.last_evaluation.get("documentError") == "bad"

    def test_not_writable_skips(self) -> None:
        home = self._home()
        engine = AlertEngine(home, registries=AlertCatalogs.default())
        with patch.object(engine._runtime, "ensure_writable", side_effect=OSError("ro")):
            report = engine.tick()
        assert report.document_error == "runtime not writable"

    def test_disabled_rule_skipped(self) -> None:
        home = self._home()
        svc = AlertRulesService(home)
        body = {**RULE, "enabled": False}
        svc.create(body)
        engine = AlertEngine(home, registries=AlertCatalogs.default())
        report = engine.tick(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert report.rules_skipped_disabled == 1
        assert report.rules_evaluated == 0

    def test_dry_run(self) -> None:
        home = self._home()
        svc = AlertRulesService(home)
        svc.create(RULE)
        engine = AlertEngine(home, registries=AlertCatalogs.default())
        rule = svc.get("demo-api-5xx-rate")
        report = engine.dry_run(rule, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert report.rule_id == "demo-api-5xx-rate"
