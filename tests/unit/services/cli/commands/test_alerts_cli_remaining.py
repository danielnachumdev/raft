"""AlertsCLI remaining branches."""
from pathlib import Path
from unittest.mock import patch
import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestAlertsCliRemaining(RaftTestCase):
    def _cli(self):
        home = Path(self.tmp_path)
        (home / "state" / "alerts").mkdir(parents=True)
        (home / "settings.yaml").write_text("notifications:\n  enabled: true\n  channels: []\n", encoding="utf-8")
        return AlertsCLI(Stack(root=home, apps=()))

    def test_test_keyerror_and_export_file(self) -> None:
        cli = self._cli()
        with pytest.raises(OperatorError):
            cli.test("missing")
        out = Path(self.tmp_path) / "out.yaml"
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say"):
            cli.export(file=str(out))
        assert out.is_file()

    def test_disable_error(self) -> None:
        cli = self._cli()
        with pytest.raises(OperatorError):
            cli.disable("missing")

    def test_summarize_branches(self) -> None:
        cli = self._cli()
        assert cli._summarize({"all": []}) == "all(...)"
        assert cli._summarize({"any": []}) == "any(...)"
