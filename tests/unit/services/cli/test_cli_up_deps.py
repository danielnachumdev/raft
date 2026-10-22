"""CLI ``raft up NAME`` dependsOn messaging and ``--no-deps``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.services.cli import RaftCLI

from tests.unit.services.cli.base import CliTestCase


class TestCliUpDeps(CliTestCase):
    def test_up_no_deps_flag(self) -> None:
        actions = MagicMock()
        actions.up.return_value = {
            "ok": True,
            "action": "up",
            "service": "app",
            "no_deps": True,
            "started_deps": [],
        }
        with patch("raft.core.core.ui.OperatorSay.say") as say, self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["up", "app", "--no-deps"]) == 0
        actions.up.assert_called_once_with("app", no_deps=True)
        say.assert_any_call("Skipping dependsOn (--no-deps).")

    def test_up_reports_started_deps(self) -> None:
        actions = MagicMock()
        actions.up.return_value = {
            "ok": True,
            "action": "up",
            "service": "frontend",
            "no_deps": False,
            "started_deps": ["demo-api"],
        }
        with patch("raft.core.core.ui.OperatorSay.say") as say, self.patched_deps(
            ServiceActions=actions
        ):
            assert RaftCLI()._invoke_fire(["up", "frontend"]) == 0
        say.assert_any_call("Bringing up dependency demo-api…")
        say.assert_any_call("Brought up demo-api.")
        say.assert_any_call("Brought up frontend.")

    def test_up_no_deps_without_name_refused(self) -> None:
        with self.patched_deps():
            with pytest.raises(RuntimeError, match="--no-deps"):
                RaftCLI()._invoke_fire(["up", "--no-deps"])
