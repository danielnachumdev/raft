"""Engine evaluate errors and prune."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.engine.engine import AlertEngine
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestEngineNotify(RaftTestCase):
    def test_eval_error_and_load_apps(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        AlertRulesService(home).create(RULE)
        engine = AlertEngine(home, registries=AlertCatalogs.default())
        with patch.object(engine._evaluator, "evaluate", return_value=("boom", [])):
            engine.tick(now=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert engine._load_apps() == []
