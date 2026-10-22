"""CLI ``raft redeploy`` dispatch for apps and control-plane aliases."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.services.cli import RaftCLI

from tests.unit.services.cli.base import CliTestCase


class TestCliRedeploy(CliTestCase):
    def test_redeploy_app_dispatch(self) -> None:
        assert self.run_main(["redeploy", "app", "--ref", "sha1", "--force-sync"]) == 0
        self.orch.redeploy_app.assert_called_once_with(
            "app", ref_override="sha1", force_sync=True
        )

    def test_redeploy_router_dispatch(self) -> None:
        actions = self._actions_ok("raft-router")
        with patch("raft.core.core.ui.OperatorSay.say"), self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["redeploy", "router"]) == 0
        actions.redeploy.assert_called_once_with("router")

    def test_redeploy_dashboard_dispatch(self) -> None:
        actions = self._actions_ok("raft-dashboard")
        with patch("raft.core.core.ui.OperatorSay.say"), self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["redeploy", "dashboard"]) == 0
        actions.redeploy.assert_called_once_with("dashboard")

    def test_redeploy_dashboard_oneshot_skips_say(self) -> None:
        actions = MagicMock()
        actions.redeploy.return_value = {
            "ok": True,
            "action": "redeploy",
            "service": "raft-dashboard",
            "started": True,
            "job_id": "job-1",
        }
        with patch("raft.core.core.ui.OperatorSay.say") as say, self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["redeploy", "dashboard"]) == 0
        say.assert_not_called()

    def test_redeploy_gate_dispatch(self) -> None:
        actions = self._actions_ok("raft-gate")
        with patch("raft.core.core.ui.OperatorSay.say"), self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["redeploy", "gate"]) == 0
        actions.redeploy.assert_called_once_with("gate")

    def test_redeploy_requires_app(self) -> None:
        with self.patched_deps():
            with pytest.raises(RuntimeError, match="redeploy requires APP"):
                RaftCLI()._invoke_fire(["redeploy"])

    def test_redeploy_unknown_app(self) -> None:
        with self.patched_deps():
            with pytest.raises(RuntimeError, match="unknown"):
                RaftCLI()._invoke_fire(["redeploy", "missing-app"])

    @staticmethod
    def _actions_ok(service: str) -> MagicMock:
        actions = MagicMock()
        actions.redeploy.return_value = {
            "ok": True,
            "action": "redeploy",
            "service": service,
        }
        return actions
