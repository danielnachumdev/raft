"""AlertStatusView firing and stale."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.service.status_view import AlertStatusView
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState, AlertRuntime
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertStatusView(RaftTestCase):
    def _home(self) -> Path:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text(
            "alerts:\n  enabled: true\n  intervalSeconds: 60\n"
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return home

    def test_firing_and_stale(self) -> None:
        home = self._home()
        AlertRulesService(home).create(RULE)
        runtime = AlertRuntimeStore(home).load()
        runtime.instances["demo-api-5xx-rate:demo-api"] = AlertInstanceState(
            rule_id="demo-api-5xx-rate",
            subject="demo-api",
            rule_hash="h",
            state="firing",
            firing_since=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_evaluated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            last_values=[],
        )
        runtime.last_evaluation = {"finishedAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}
        AlertRuntimeStore(home).save(runtime)
        view = AlertStatusView(home).build()
        assert view["rules"]["demo-api-5xx-rate"]["state"] == "firing"
        assert view["stale"] is True
