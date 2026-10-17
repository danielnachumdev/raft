"""Engine prune and rule-hash reset."""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from raft.core.observe.alerts.engine.engine import AlertEngine
from raft.core.observe.alerts.model.document import AlertRulesDocument
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from raft.core.observe.alerts.catalogs import AlertCatalogs
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.engine.test_engine_helpers import FakeHttp, FakeNotifier
from tests.unit.core.observe.alerts.engine.test_engine import _engine
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestEnginePrune(RaftTestCase):
    def test_prune_stale_instance(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        svc = AlertRulesService(home)
        svc.create({**RULE, "enabled": False})
        rt = AlertRuntimeStore(home).load()
        rt.instances["x"] = AlertInstanceState(
            "demo-api-5xx-rate", "demo-api", "h", "pending",
            pending_since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_values=[],
        )
        AlertRuntimeStore(home).save(rt)
        AlertEngine(home, registries=AlertCatalogs.default()).tick(
            now=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        assert "x" not in AlertRuntimeStore(home).load().instances

    def test_rule_hash_reset(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        fake = FakeHttp(0.1)
        engine = _engine(home, fake)
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        engine.tick(now=now)
        store = AlertRulesService(home)
        cond = {
            **RULE["condition"],
            "params": {**RULE["condition"]["params"], "value": 0.01},
        }
        store.replace("demo-api-5xx-rate", {**RULE, "condition": cond})
        engine.tick(now=now + timedelta(minutes=1))
