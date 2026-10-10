"""Shared CLI test case with mocked stack/orchestrator."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest

from raft import cli

from ..base import RaftTestCase, make_app, make_stack, write_demo_inventory

# Where CLI modules bind names imported from ``raft.cli.deps``.
_DEP_TARGETS = {
    "load_stack": ("raft.cli.root",),
    "load_config": ("raft.cli.root",),
    "setup_logging": ("raft.cli.root",),
    "AppApply": ("raft.cli.root",),
    "Orchestrator": ("raft.cli.root", "raft.cli.gate"),
    "Doctor": ("raft.cli.root",),
    "Status": ("raft.cli.root",),
    "Serve": ("raft.cli.root",),
    "Logs": ("raft.cli.root",),
    "Purge": ("raft.cli.root",),
    "SelfUpdate": ("raft.cli.root",),
    "Uninstall": ("raft.cli.root",),
    "GitAuthManager": ("raft.cli.auth",),
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
            return cli.main(argv)

    def run_cli(self, argv: list[str]) -> None:
        with self.patched_deps(Orchestrator=self.orch):
            cli.run(argv)

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
