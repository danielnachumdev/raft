"""Shared helpers for adapter tests."""

from unittest.mock import MagicMock

import pytest

from raft.adapters import DockerStack

from ..base import RaftTestCase, completed, make_local_stack, write_applied_app


class AdapterTestCase(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _adapter_setup(self, _raft_base) -> None:
        write_applied_app(self.tmp_path, "app")
        self.stack = make_local_stack(self.tmp_path)
        self.app = self.stack.apps[0]
        self.shell = MagicMock()

    def docker_stack(self) -> DockerStack:
        return DockerStack(self.stack, self.shell)

    @staticmethod
    def ok(stdout: str = "", returncode: int = 0) -> MagicMock:
        return completed(stdout=stdout, returncode=returncode)
