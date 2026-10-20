"""RulesService conflicts and channels."""
from pathlib import Path
import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.service.rules_service import AlertRulesService, RuleConflict
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestRulesServiceEdges(RaftTestCase):
    def _svc(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: false\n  channels:\n"
            "    - id: ops\n      type: webhook\n      settings: {url: https://192.0.2.1/x}\n",
            encoding="utf-8",
        )
        return AlertRulesService(home)

    def test_conflict_and_channels(self) -> None:
        svc = self._svc()
        svc.create(RULE)
        with pytest.raises(RuleConflict):
            svc.create(RULE)
        body = {**RULE, "channelIds": ["ops"]}
        rep = svc.validate_rule(body)
        assert any("notifications.enabled" in w.message for w in rep.warnings)
        with pytest.raises(OperatorError):
            svc.create({**RULE, "id": "other", "channelIds": ["missing"]})
