"""CLI ``raft dashboard`` smoke (writer paths; no Docker)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.lifecycle.dashboard.service import DashboardService
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from raft.services.cli.commands.dashboard import DashboardCLI
from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.lifecycle.dashboard.oauth_test_helpers import seed_oauth_secrets


class TestDashboardCLI(RaftTestCase):
    def _cli(self) -> DashboardCLI:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n", encoding="utf-8"
        )
        writer = DashboardSettingsWriter(home)
        svc = DashboardService(
            StackMakers.make_stack(home),
            orchestrator=MagicMock(),
            docker=MagicMock(),
            writer=writer,
        )
        return DashboardCLI(StackMakers.make_stack(home), service=svc)

    def test_status_enable_disable_set_password(self) -> None:
        cli = self._cli()
        with patch("raft.services.cli.commands.dashboard.OperatorSay.say") as say:
            cli.set_password("correct-horse")
            cli.enable()
            cli.status()
            cli.status(json=True)
            cli.disable()
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "enabled" in dumped.lower() or "raft-dashboard" in dumped

    def test_oauth_init_and_allowlist(self) -> None:
        cli = self._cli()
        allow = Path(self.tmp_path) / "allow.txt"
        allow.write_text("ops@example.com\n", encoding="utf-8")
        with patch("raft.services.cli.commands.dashboard_oauth.OperatorSay.say") as say:
            cli.oauth.init(provider="google")
            cli.oauth.init(provider="google", json=True)
            cli.oauth.allowlist_set(str(allow))
            cli.oauth.allowlist_add("other@example.com")
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "redirect" in dumped.lower()
        assert "allowlist" in dumped.lower()

    def test_status_prints_oauth_fields(self) -> None:
        cli = self._cli()
        seed_oauth_secrets(Path(self.tmp_path))
        with patch("raft.services.cli.commands.dashboard.OperatorSay.say") as say:
            cli.enable(
                public_host="ops.example.com",
                tls="acme",
                auth_mode="oauth",
            )
            cli.status()
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "auth.oauth.provider" in dumped
        assert "secretsReady" in dumped
