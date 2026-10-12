"""Shared CLI test case with mocked stack/orchestrator."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest

from raft.services.cli import RaftCLI

from tests.unit.base import RaftTestCase, AppMakers, AppliedInventory, StackMakers

# Where CLI modules bind names imported from ``raft.services.cli.utils.deps``.
_DEP_TARGETS = {
    "load_stack": ("raft.services.cli.commands.raft_commands",),
    "SettingsLoader": ("raft.services.cli.commands.raft_commands",),
    "HostLogging": ("raft.services.cli.commands.raft_commands",),
    "AppApply": ("raft.services.cli.commands.raft_commands",),
    "Orchestrator": ("raft.services.cli.commands.raft_commands", "raft.services.cli.commands.gate"),
    "Doctor": ("raft.services.cli.commands.raft_commands",),
    "Status": ("raft.services.cli.commands.raft_commands",),
    "Serve": ("raft.services.cli.commands.raft_commands",),
    "Logs": ("raft.services.cli.commands.raft_commands",),
    "Purge": ("raft.services.cli.commands.raft_commands",),
    "SelfUpdate": ("raft.services.cli.commands.raft_commands",),
    "Uninstall": ("raft.services.cli.commands.raft_commands",),
    "GitAuthManager": ("raft.services.cli.commands.auth",),
}


class CliTestCase(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _cli_setup(self, _raft_base) -> None:
        AppliedInventory.write_demo_inventory(self.tmp_path)
        self.stack = StackMakers.make_stack(
            self.tmp_path,
            (
                AppMakers.make_app("app"),
                AppMakers.make_app("other"),
            ),
        )
        self.orch = MagicMock()

    def run_main(self, argv: list[str]) -> int:
        with self.patched_deps(Orchestrator=self.orch):
            return RaftCLI()._invoke_fire(argv)

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
