"""AlertsCLI json output paths."""
from pathlib import Path
from unittest.mock import patch
import yaml
from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestAlertsCliJson(RaftTestCase):
    def _cli(self):
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text("notifications:\n  enabled: true\n  channels: []\n", encoding="utf-8")
        return AlertsCLI(Stack(root=home, apps=()))

    def test_list_show_status_json(self) -> None:
        cli = self._cli()
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8")
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say") as say:
            cli.apply(str(path))
            cli.list(json=True)
            cli.show("demo-api-5xx-rate", json=True)
            cli.status(json=True)
            cli.dry_run("demo-api-5xx-rate", json=True)
            assert say.called
