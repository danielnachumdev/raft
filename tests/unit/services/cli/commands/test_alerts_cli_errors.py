"""AlertsCLI error paths."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertsCliErrors(RaftTestCase):
    def _cli(self) -> AlertsCLI:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "alerts:\n  enabled: true\n  intervalSeconds: 30\n"
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return AlertsCLI(Stack(root=home, apps=()))

    def test_missing_rule_errors(self) -> None:
        cli = self._cli()
        with pytest.raises(OperatorError):
            cli.show("missing")
        with pytest.raises(OperatorError):
            cli.delete("missing")

    def test_dry_run_errors(self) -> None:
        cli = self._cli()
        with pytest.raises(OperatorError):
            cli._dry_run_rules(rule_id=None, file=None, rule=None)
        with pytest.raises(OperatorError):
            cli._dry_run_rules(rule_id="missing", file=None, rule=None)

    def test_read_file_error(self) -> None:
        cli = self._cli()
        with pytest.raises(OperatorError):
            cli._read_file(str(Path(self.tmp_path) / "nope.yaml"))
