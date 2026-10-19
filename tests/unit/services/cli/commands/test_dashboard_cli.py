"""CLI ``raft dashboard`` smoke (writer paths; no Docker)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.lifecycle.dashboard.service import DashboardService
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from raft.services.cli.commands.dashboard import DashboardCLI
from tests.unit.base import RaftTestCase, StackMakers


class TestDashboardCLI(RaftTestCase):
    def _cli(self) -> DashboardCLI:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n", encoding="utf-8"
        )
        writer = DashboardSettingsWriter(home)
        docker = MagicMock()
        orch = MagicMock()
        svc = DashboardService(
            StackMakers.make_stack(home),
            orchestrator=orch,
            docker=docker,
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
