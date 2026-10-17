"""AlertRulesService CRUD."""

from pathlib import Path

import pytest

from raft.core.observe.alerts.service.rules_service import AlertRulesService
from tests.unit.base import RaftTestCase

RULE = {
    "id": "demo-api-5xx-rate",
    "name": "demo-api 5xx",
    "severity": "error",
    "for": "0s",
    "cooldown": "15m",
    "condition": {
        "signal": "metrics.http",
        "select": {"target": "demo-api", "metric": "error_rate_5xx"},
        "kind": "threshold",
        "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 0.05},
    },
}

OTHER = {
    **RULE,
    "id": "demo-web-cpu",
    "name": "cpu",
    "condition": {
        "signal": "metrics.resources",
        "select": {"target": "demo-web", "metric": "cpu_percent"},
        "kind": "threshold",
        "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 85},
    },
}


class TestAlertRulesService(RaftTestCase):
    def _svc(self) -> AlertRulesService:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return AlertRulesService(home)

    def test_create_get_replace_enable_delete(self) -> None:
        svc = self._svc()
        assert svc.create(RULE).id == "demo-api-5xx-rate"
        assert svc.replace("demo-api-5xx-rate", {**RULE, "name": "renamed"}).name == "renamed"
        assert svc.set_enabled("demo-api-5xx-rate", False).enabled is False
        svc.delete("demo-api-5xx-rate")
        with pytest.raises(KeyError):
            svc.get("demo-api-5xx-rate")

    def test_apply_prune_deletes(self) -> None:
        svc = self._svc()
        svc.create(RULE)
        summary = svc.apply_document({"version": 1, "rules": [OTHER]}, prune=True)
        assert "demo-api-5xx-rate" in summary.deleted

    def test_apply_creates_new(self) -> None:
        svc = self._svc()
        svc.create(RULE)
        summary = svc.apply_document({"version": 1, "rules": [OTHER]}, prune=True)
        assert "demo-web-cpu" in summary.created

    def test_validate(self) -> None:
        svc = self._svc()
        assert svc.validate_rule(RULE).ok
        assert not svc.validate_document({"version": 2, "rules": []}).ok
