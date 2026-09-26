"""Shared CLI test case with mocked stack/orchestrator."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from typing import Iterator, Optional
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
            exited.enter_context(patch("raft.cli.deps.load_stack", return_value=stack))
            for name, value in dep_returns.items():
                patches[name] = exited.enter_context(
                    patch(f"raft.cli.deps.{name}", return_value=value)
                )
            yield patches
