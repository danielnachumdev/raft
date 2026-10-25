"""CLI alert recommendation commands."""

from pathlib import Path
from unittest.mock import patch

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.alerts.service.rules_service import RuleConflict
from raft.services.cli.commands.alerts import AlertsCLI
from tests.unit.base import RaftTestCase


class TestAlertsCliRecommendations(RaftTestCase):
    def _cli(self) -> AlertsCLI:
        home = Path(self.tmp_path)
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels: []\n",
            encoding="utf-8",
        )
        return AlertsCLI(Stack(root=home, apps=()))

    def test_recommendations_apply_dismiss(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.alerts_output.OperatorSay.say") as say:
            cli.recommendations()
            cli.recommendations(json=True)
            cli.apply_recommendation("any-service-oom")
            cli.dismiss("any-service-high-memory")
        text = " ".join(str(c.args[0]) for c in say.call_args_list)
        assert "any-service-oom" in text or "Created" in text

    def test_apply_unknown(self) -> None:
        cli = self._cli()
        try:
            cli.apply_recommendation("nope")
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "unknown alert recommendation" in str(exc)

    def test_apply_conflict(self) -> None:
        cli = self._cli()
        with patch.object(
            cli._recommendations, "apply", side_effect=RuleConflict("dup")
        ):
            try:
                cli.apply_recommendation("any-service-oom")
                raise AssertionError("expected OperatorError")
            except OperatorError as exc:
                assert "dup" in str(exc)
