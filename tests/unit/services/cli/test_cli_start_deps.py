"""CLI ``raft start`` dependsOn messaging and ``--no-deps``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.services.cli import RaftCLI

from tests.unit.services.cli.base import CliTestCase


class TestCliStartDeps(CliTestCase):
    def test_start_no_deps_flag(self) -> None:
        actions = MagicMock()
        actions.start.return_value = {
            "ok": True,
            "action": "start",
            "service": "app",
            "no_deps": True,
            "started_deps": [],
        }
        with patch("raft.core.core.ui.OperatorSay.say") as say, self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["start", "app", "--no-deps"]) == 0
        actions.start.assert_called_once_with("app", no_deps=True)
        say.assert_any_call("Skipping dependsOn (--no-deps).")

    def test_start_reports_started_deps(self) -> None:
        actions = MagicMock()
        actions.start.return_value = {
            "ok": True,
            "action": "start",
            "service": "frontend",
            "no_deps": False,
            "started_deps": ["demo-api"],
        }
        with patch("raft.core.core.ui.OperatorSay.say") as say, self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["start", "frontend"]) == 0
        say.assert_any_call("Starting dependency demo-api…")
        say.assert_any_call("Started demo-api.")
        say.assert_any_call("Started frontend.")
