"""Final CLI summarize / dry-run file rule."""

from pathlib import Path
from unittest.mock import patch

import yaml

from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertsCliFinal(RaftTestCase):
    def _cli(self) -> AlertsCLI:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        (home / "settings.yaml").write_text(
            "alerts: {enabled: true, intervalSeconds: 30}\n"
            "notifications: {enabled: true, channels: []}\n",
            encoding="utf-8",
        )
        return AlertsCLI(Stack(root=home, apps=()))

    def test_summarize(self) -> None:
        cli = self._cli()
        assert cli._summarize({"all": []}) == "all(...)"
        assert cli._summarize({"any": []}) == "any(...)"
        assert cli._summarize("x") == "?"
        assert (
            cli._summarize({"signal": "metrics.http", "kind": "threshold"})
            == "metrics.http threshold"
        )

    def test_dry_run_named_rule(self) -> None:
        cli = self._cli()
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8"
        )
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            assert len(cli._dry_run_from_file(str(path), "demo-api-5xx-rate")) == 1
