"""AlertStatusView pending and errors."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.service.status_view import AlertStatusView
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestStatusViewEdges(RaftTestCase):
    def _home(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "alerts:\n  enabled: true\n  intervalSeconds: 60\nnotifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return home

    def test_pending_and_load_error(self) -> None:
        home = self._home()
        AlertRulesService(home).create({**RULE, "id": "demo-web-cpu", "name": "cpu"})
        rt = AlertRuntimeStore(home).load()
        rt.instances["demo-web-cpu:demo-web"] = AlertInstanceState(
            "demo-web-cpu", "demo-web", "h", "pending",
            pending_since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_values=[],
        )
        AlertRuntimeStore(home).save(rt)
        view = AlertStatusView(home).build()
        assert view["rules"]["demo-web-cpu"]["state"] == "pending"

    def test_stale_bad_timestamp(self) -> None:
        home = self._home()
        AlertRulesService(home).create(RULE)
        rt = AlertRuntimeStore(home).load()
        rt.last_evaluation = {"finishedAt": "not-a-date"}
        AlertRuntimeStore(home).save(rt)
        assert AlertStatusView(home).build()["stale"] is True
