"""HostOneshotAlive docker inspect probe."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from raft.core.platform.adapters.docker.host_oneshot_alive import HostOneshotAlive


class TestHostOneshotAlive:
    def test_empty_id_false(self) -> None:
        shell = MagicMock()
        assert HostOneshotAlive(shell).running("") is False
        shell.run.assert_not_called()

    def test_running_true(self) -> None:
        shell = MagicMock()
        shell.run.return_value = SimpleNamespace(returncode=0, stdout="true\n")
        assert HostOneshotAlive(shell).running("cid-1") is True

    def test_not_running_or_missing(self) -> None:
        shell = MagicMock()
        shell.run.return_value = SimpleNamespace(returncode=1, stdout="")
        assert HostOneshotAlive(shell).running("cid-missing") is False
        shell.run.return_value = SimpleNamespace(returncode=0, stdout="false\n")
        assert HostOneshotAlive(shell).running("cid-exited") is False
