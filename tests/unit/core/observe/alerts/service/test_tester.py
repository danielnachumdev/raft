"""AlertTester send."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from raft.core.observe.alerts.service.tester import AlertTester
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestAlertTester(RaftTestCase):
    def test_send_missing(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        with pytest.raises(KeyError):
            AlertTester(home).send("missing")

    def test_send_ok(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text("notifications:\n  enabled: true\n  channels: []\n", encoding="utf-8")
        from raft.core.observe.alerts.service.rules_service import AlertRulesService
        AlertRulesService(home).create(RULE)
        with patch("raft.core.observe.alerts.service.tester.Notifier") as N:
            N.return_value.deliver.return_value = []
            assert AlertTester(home).send("demo-api-5xx-rate") == []
