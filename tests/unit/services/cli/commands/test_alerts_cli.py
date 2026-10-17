"""CLI ``raft alerts`` commands."""

from pathlib import Path
from unittest.mock import patch

import yaml

from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
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


class TestAlertsCLI(RaftTestCase):
    def _cli(self) -> AlertsCLI:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return AlertsCLI(Stack(root=home, apps=()))

    def _rules_file(self) -> Path:
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8"
        )
        return path

    def test_apply_and_list(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            cli.apply(str(self._rules_file()))
            cli.list()

    def test_show_status_export(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            cli.apply(str(self._rules_file()))
            cli.show("demo-api-5xx-rate")
            cli.status()
            cli.export()

    def test_validate_enable_dry_run_delete(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            cli.apply(str(self._rules_file()))
            cli.validate()
            cli.enable("demo-api-5xx-rate")
            cli.dry_run("demo-api-5xx-rate")
            cli.delete("demo-api-5xx-rate")
