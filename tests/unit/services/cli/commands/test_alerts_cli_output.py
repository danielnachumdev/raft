"""AlertsCliOutput helpers."""

from unittest.mock import MagicMock, patch

from raft.services.cli.commands.alerts_output import AlertsCliOutput
from tests.unit.base import RaftTestCase

_SUBJECT = {
    "subject": "demo-api",
    "matched": True,
    "currentState": "ok",
    "wouldState": "firing",
    "wouldNotify": "firing",
    "leaves": [{"detail": "d"}],
}


class TestAlertsCliOutput(RaftTestCase):
    def test_tables_and_prints(self) -> None:
        out = AlertsCliOutput()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say") as say:
            out.list_table([])
            out.recommendations_table([])
            out.recommendations_table(
                [{"id": "any-service-oom", "kind": "setup", "title": "OOM"}]
            )
            out.say_yaml({"a": 1})
            out.say_json({"a": 1})
            out.print_validation(
                {"ok": False, "errors": [{"path": "p", "message": "m"}], "warnings": []}
            )
            out.print_dry_run({"error": "e", "subjects": [_SUBJECT]})
            item = MagicMock(
                channel_id="ops",
                type_id="webhook",
                result=MagicMock(status=MagicMock(value="success"), error=None),
            )
            out.print_deliveries([item])
            assert say.called
            said = " ".join(str(c.args[0]) for c in say.call_args_list)
            assert "No open alert recommendations." in said
            assert "any-service-oom" in said
