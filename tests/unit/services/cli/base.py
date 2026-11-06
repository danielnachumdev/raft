"""Shared CLI test case with mocked stack/orchestrator."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest

from raft.services.cli import RaftCLI
from raft.services.cli.utils.deps import lazy

from tests.unit.base import RaftTestCase, AppMakers, AppliedInventory, StackMakers


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
        real = lazy.call
        factories = {
            name: MagicMock(return_value=value) for name, value in dep_returns.items()
        }

        def call(name: str, *args, **kwargs):
            if name == "load_stack":
                return stack
            factory = factories.get(name)
            if factory is not None:
                return factory(*args, **kwargs)
            return real(name, *args, **kwargs)

        with patch.object(lazy, "call", call):
            yield factories
