"""Shared CLI test case with mocked stack/orchestrator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft import cli

from ..base import RaftTestCase, make_app, make_stack, write_demo_inventory


class CliTestCase(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _cli_setup(self, _raft_base) -> None:
        write_demo_inventory(self.tmp_path)
        self.stack = make_stack(
            self.tmp_path,
            (
                make_app("app"),
                make_app("other"),
            ),
        )
        self.orch = MagicMock()

    def run_main(self, argv: list[str]) -> int:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator", return_value=self.orch):
                return cli.main(argv)

    def run_cli(self, argv: list[str]) -> None:
        with patch("raft.cli.deps.load_stack", return_value=self.stack):
            with patch("raft.cli.deps.Orchestrator", return_value=self.orch):
                cli.run(argv)
