"""AlertsCLI dry-run from file."""

from pathlib import Path

import pytest
import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertsCliDryRun(RaftTestCase):
    def _cli(self) -> AlertsCLI:
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "settings.yaml").write_text("notifications:\n  enabled: true\n  channels: []\n", encoding="utf-8")
        return AlertsCLI(Stack(root=home, apps=()))

    def test_from_file(self) -> None:
        cli = self._cli()
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8")
        with pytest.raises(OperatorError):
            cli._dry_run_rules(rule_id=None, file=str(path), rule="missing")
        assert len(cli._dry_run_rules(rule_id=None, file=str(path), rule=None)) == 1
