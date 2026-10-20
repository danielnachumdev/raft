"""RulesService replace, unchanged apply, no-prune."""
from pathlib import Path

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.service.rules_service import AlertRulesService
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE, OTHER


class TestRulesServiceMore(RaftTestCase):
    def _svc(self) -> AlertRulesService:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return AlertRulesService(home)

    def test_replace_errors(self) -> None:
        svc = self._svc()
        with pytest.raises(KeyError):
            svc.replace("missing", RULE)
        svc.create(RULE)
        with pytest.raises(OperatorError):
            svc.replace("demo-api-5xx-rate", {**RULE, "id": "other"})

    def test_apply_unchanged_and_keep(self) -> None:
        svc = self._svc()
        svc.create(RULE)
        same = svc.apply_document({"version": 1, "rules": [RULE]}, prune=False)
        assert "demo-api-5xx-rate" in same.unchanged
        both = svc.apply_document({"version": 1, "rules": [RULE]}, prune=False)
        assert len(both.deleted) == 0
        svc.apply_document({"version": 1, "rules": [OTHER]}, prune=False)
        assert svc.get("demo-api-5xx-rate").id == "demo-api-5xx-rate"
