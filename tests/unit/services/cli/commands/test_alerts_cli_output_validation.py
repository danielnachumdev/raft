"""AlertsCliOutput validation ok and warnings."""
from unittest.mock import patch

from raft.services.cli.commands.alerts_output import AlertsCliOutput
from tests.unit.base import RaftTestCase


class TestAlertsCliOutputValidation(RaftTestCase):
    def test_ok_and_warning(self) -> None:
        out = AlertsCliOutput()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say") as say:
            out.print_validation(
                {"ok": True, "ruleCount": 1, "errors": [], "warnings": [{"path": "w", "message": "m"}]}
            )
            assert say.called
