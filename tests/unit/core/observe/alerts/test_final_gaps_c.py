"""Final coverage gaps C: status + CLI output + event duration."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from raft.core.observe.alerts.engine.event_factory import AlertEventFactory
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.service.status_view import AlertStatusView
from raft.core.observe.alerts.store.runtime_state import (
    AlertInstanceState,
    AlertRuntime,
)
from raft.core.observe.alerts.store.runtime_store import AlertRuntimeStore
from raft.services.cli.commands.alerts_output import AlertsCliOutput
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestFinalGapsC(RaftTestCase):
    def _home(self) -> Path:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "alerts: {enabled: true, intervalSeconds: 30}\n"
            "notifications: {enabled: false, channels: []}\n",
            encoding="utf-8",
        )
        return home

    def test_status_firing(self) -> None:
        home = self._home()
        AlertRulesService(home).create(RULE)
        runtime = AlertRuntime.empty()
        runtime.instances["a"] = AlertInstanceState(
            rule_id="demo-api-5xx-rate",
            subject="demo-api",
            rule_hash="h",
            state="firing",
            firing_since=NOW,
        )
        AlertRuntimeStore(home).save(runtime)
        assert AlertStatusView(home).build()["rules"]["demo-api-5xx-rate"]["state"] == "firing"

    def test_stale_and_output(self) -> None:
        assert AlertStatusView._stale({"finishedAt": "bad"}, 30, True, True) is True
        out = AlertsCliOutput()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"), patch(
            "raft.services.cli.commands.alerts_output.OperatorSay.say_err"
        ):
            out.say_err("e")
            out.print_validation(
                {"ok": False, "errors": [], "warnings": [{"path": "w", "message": "m"}]}
            )
        fac = AlertEventFactory()
        assert fac._duration(NOW, NOW + timedelta(seconds=120)) == "2m"
        assert fac._duration(NOW, NOW + timedelta(seconds=7200)) == "2h"
