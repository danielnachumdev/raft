"""Composable unit-test base: tmp raft home + common stack facades."""

from pathlib import Path
from typing import Any

import pytest

from raft.core.core.models.stack import Stack

from .applied_inventory import AppliedInventory
from .shell_mocks import ShellMocks
from .stack_makers import StackMakers
from .stack_render import StackRender


class RaftTestCase(StackMakers, AppliedInventory, StackRender, ShellMocks):
    @pytest.fixture(autouse=True)
    def _raft_base(self, tmp_path: Path, isolated_raft_ssh_dir: Path) -> None:
        self.tmp_path = tmp_path
        self.ssh_dir = isolated_raft_ssh_dir
        self.ensure_orchestrator_root(tmp_path)

    def local_stack(self, *names: str, **kwargs) -> Stack:
        return self.make_local_stack(self.tmp_path, *names, **kwargs)

    def git_stack(self, **kwargs) -> Stack:
        return self.make_git_stack(self.tmp_path, **kwargs)

    def demo_repo(self) -> Path:
        return self.write_demo_inventory(self.tmp_path)

    def ensure_checkouts(self, *names: str) -> None:
        self.ensure_app_checkouts(self.tmp_path, *names)

    def render_applied(self, *, edge: Any = None) -> Path:
        return self.render_stack(self.tmp_path, edge=edge)

    def write_home_settings(self, body: Any) -> Path:
        return self.write_settings(self.tmp_path, body)
