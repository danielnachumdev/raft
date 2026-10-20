"""AlertsCLI status text with instances."""

from pathlib import Path
from unittest.mock import patch

import yaml

from raft.core.core.models.stack import Stack
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

_STATUS = {
    "stale": True,
    "enabled": True,
    "intervalSeconds": 30,
    "lastEvaluation": {"finishedAt": "t", "errors": []},
    "instances": [{"fingerprint": "a", "state": "firing", "suppressed": False}],
}


class TestAlertsCliStatusInstances(RaftTestCase):
    def test_status_lists_instances(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        cli = AlertsCLI(Stack(root=home, apps=()))
        path = home / "rules.yaml"
        path.write_text(yaml.safe_dump({"version": 1, "rules": [RULE]}), encoding="utf-8")
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say") as say:
            cli.apply(str(path))
            with patch(
                "raft.services.cli.commands.alerts.AlertStatusView"
            ) as View:
                View.return_value.build.return_value = _STATUS
                cli.status()
            assert say.called

    def test_status_json_skips_stale_warning(self) -> None:
        home = Path(self.tmp_path)
        cli = AlertsCLI(Stack(root=home, apps=()))
        fresh = {**_STATUS, "stale": False}
        with patch("raft.services.cli.commands.alerts.AlertStatusView") as View:
            View.return_value.build.return_value = fresh
            with patch(
                "raft.services.cli.commands.alerts_output.AlertsCliOutput.say_json"
            ) as sj:
                cli.status(json=True)
                assert sj.called
