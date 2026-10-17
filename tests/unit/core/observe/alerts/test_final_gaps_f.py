"""Final coverage gaps F: status + channel warnings."""

from pathlib import Path

from raft.core.observe.alerts.model.issues import ValidationReport
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from raft.core.observe.alerts.service.status_view import AlertStatusView
from raft.core.observe.alerts.store.runtime_state import (
    AlertInstanceState,
    AlertRuntime,
)
from tests.unit.base import RaftTestCase


class TestFinalGapsF(RaftTestCase):
    def test_status_skip_and_ok_row(self) -> None:
        runtime = AlertRuntime.empty()
        runtime.instances["other"] = AlertInstanceState(
            rule_id="other", subject="x", rule_hash="h", state="firing"
        )
        counts = AlertStatusView._counts("demo-api-5xx-rate", runtime)
        assert counts["firing"] == 0
        assert (
            AlertStatusView._instance_row(
                "fp",
                AlertInstanceState(
                    rule_id="missing", subject="x", rule_hash="h", state="ok"
                ),
                {},
            )
            is None
        )

    def test_channel_warnings_non_map(self) -> None:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        (home / "settings.yaml").write_text(
            "notifications: {enabled: false, channels: []}\n", encoding="utf-8"
        )
        report = ValidationReport()
        AlertRulesService(home)._channel_warnings("bad", report)
        assert not report.warnings
