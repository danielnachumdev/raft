"""AlertsCLI test command."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import yaml
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.delivery_status import DeliveryStatus
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestAlertsCliTest(RaftTestCase):
    def test_test_command(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text("notifications:\n  enabled: true\n  channels: []\n", encoding="utf-8")
        cli = AlertsCLI(Stack(root=home, apps=()))
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8")
        cli.apply(str(path))
        ok = MagicMock()
        ok.result.status = DeliveryStatus.SUCCESS
        ok.result.error = None
        ok.channel_id = "ops"
        ok.type_id = "webhook"
        with patch("raft.services.cli.commands.alerts.AlertTester") as T:
            T.return_value.send.return_value = [ok]
            cli.test("demo-api-5xx-rate")
