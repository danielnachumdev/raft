"""Shared CLI test case with mocked stack/orchestrator."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest

from raft.cli import RaftCLI

from ..base import RaftTestCase, make_app, make_stack, write_demo_inventory

# Where CLI modules bind names imported from ``raft.cli.utils.deps``.
_DEP_TARGETS = {
    "load_stack": ("raft.cli.cli_commands",),
    "load_config": ("raft.cli.cli_commands",),
    "setup_logging": ("raft.cli.cli_commands",),
    "AppApply": ("raft.cli.cli_commands",),
    "Orchestrator": ("raft.cli.cli_commands", "raft.cli.commands.gate"),
    "Doctor": ("raft.cli.cli_commands",),
    "Status": ("raft.cli.cli_commands",),
    "Serve": ("raft.cli.cli_commands",),
    "Logs": ("raft.cli.cli_commands",),
    "Purge": ("raft.cli.cli_commands",),
    "SelfUpdate": ("raft.cli.cli_commands",),
    "Uninstall": ("raft.cli.cli_commands",),
    "GitAuthManager": ("raft.cli.commands.auth",),
}


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
        with self.patched_deps(Orchestrator=self.orch):
            return RaftCLI()._main(argv)

    def run_cli(self, argv: list[str]) -> None:
        with self.patched_deps(Orchestrator=self.orch):
            RaftCLI().run(argv)

    @contextmanager
    def patched_deps(
        self,
        *,
        stack=None,
        **dep_returns: Optional[MagicMock],
    ) -> Iterator[dict]:
        stack = self.stack if stack is None else stack
        patches: dict = {}
        with ExitStack() as exited:
            for target in _DEP_TARGETS["load_stack"]:
                exited.enter_context(patch(f"{target}.load_stack", return_value=stack))
            for name, value in dep_returns.items():
                mocks = [
                    exited.enter_context(
                        patch(f"{target}.{name}", return_value=value)
                    )
                    for target in _DEP_TARGETS[name]
                ]
                patches[name] = mocks[0]
            yield patches
