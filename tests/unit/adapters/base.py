"""Shared helpers for adapter tests."""

from unittest.mock import MagicMock

from raft.adapters import DockerStack

from ..base import AppliedStackCase, ShellMocks


class AdapterTestCase(AppliedStackCase):
    def docker_stack(self) -> DockerStack:
        return DockerStack(self.stack, self.shell)

    @staticmethod
    def ok(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
        return ShellMocks.completed(stdout=stdout, returncode=returncode, stderr=stderr)
