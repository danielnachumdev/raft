"""AlertStatusView suppressed and document error."""
from datetime import datetime, timezone
from pathlib import Path

from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.service.status_view import AlertStatusView
from raft.core.observe.alerts.store.runtime_state import AlertInstanceState
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestStatusViewComplete(RaftTestCase):
    def _home(self) -> Path:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text(
            "alerts:\n  enabled: false\n  intervalSeconds: 60\n"
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return home

    def test_document_error_and_suppressed(self) -> None:
        home = self._home()
        (home / "state" / "alerts" / "rules.yaml").write_text("version: 2\n", encoding="utf-8")
        view = AlertStatusView(home).build()
        assert view["documentError"]
        (home / "state" / "alerts" / "rules.yaml").unlink()
        AlertRulesService(home).create(RULE)
        rt = AlertRuntimeStore(home).load()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rt.instances["a"] = AlertInstanceState(
            "demo-api-5xx-rate", "demo-api", "h", "firing",
            firing_since=now, suppressed=True, last_evaluated_at=now, last_values=[],
        )
        AlertRuntimeStore(home).save(rt)
        disabled = AlertRulesService(home).set_enabled("demo-api-5xx-rate", False)
        assert disabled.enabled is False
        body = AlertStatusView(home).build()
        assert body["rules"]["demo-api-5xx-rate"]["state"] == "disabled"
        assert body["stale"] is False
