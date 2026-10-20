"""Rules service channel warnings on document validate."""
from pathlib import Path

from raft.core.observe.alerts.service.rules_service import AlertRulesService
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestRulesValidateWarn(RaftTestCase):
    def test_channel_warning_on_document(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: false\n  channels:\n"
            "    - id: ops\n      type: webhook\n      settings: {url: https://192.0.2.1/x}\n",
            encoding="utf-8",
        )
        svc = AlertRulesService(home)
        rep = svc.validate_document(
            {"version": 1, "rules": [{**RULE, "channelIds": ["ops"]}]}
        )
        assert any("notifications.enabled" in w.message for w in rep.warnings)

    def test_channel_warnings_non_mapping(self) -> None:
        home = Path(self.tmp_path)
        svc = AlertRulesService(home)
        rep = svc.validate_document({"version": 1, "rules": []})
        svc._channel_warnings([], rep)
        assert rep.ok