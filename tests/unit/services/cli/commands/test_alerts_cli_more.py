"""Additional CLI alerts coverage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.delivery_status import DeliveryStatus
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertsCliMore(RaftTestCase):
    def _cli(self) -> AlertsCLI:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "alerts: {enabled: true, intervalSeconds: 30}\n"
            "notifications: {enabled: true, channels: []}\n",
            encoding="utf-8",
        )
        return AlertsCLI(Stack(root=home, apps=()))

    def test_json_paths_and_validate_fail(self) -> None:
        cli = self._cli()
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8"
        )
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            cli.apply(str(path))
            cli.list(json=True)
            cli.show("demo-api-5xx-rate", json=True)
            cli.dry_run("demo-api-5xx-rate", json=True)
            cli.status(json=True)
            cli.disable("demo-api-5xx-rate")
        bad = Path(self.tmp_path) / "bad.yaml"
        bad.write_text("rules: [1]\n", encoding="utf-8")
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"), patch(
            "raft.services.cli.commands.alerts_output.OperatorSay.say_err"
        ):
            with pytest.raises(SystemExit):
                cli.validate(file=str(bad))

    def test_test_exit_and_load_raw(self) -> None:
        cli = self._cli()
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8"
        )
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            cli.apply(str(path))
        with patch("raft.services.cli.commands.alerts.AlertTester") as Tester:
            fail = MagicMock()
            fail.result.status = DeliveryStatus.FAILED
            fail.result.error = "boom"
            fail.channel_id = "ops"
            fail.type_id = "webhook"
            Tester.return_value.send.return_value = [fail]
            with pytest.raises(SystemExit):
                cli.test("demo-api-5xx-rate")
        (Path(self.tmp_path) / "host" / "alerts" / "rules.yaml").unlink()
        assert cli._load_raw(None) == {"version": 1, "rules": []}
        with pytest.raises(OperatorError):
            cli._read_file(str(Path(self.tmp_path) / "missing.yaml"))
