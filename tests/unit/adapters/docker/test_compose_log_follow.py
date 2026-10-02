"""Unit tests for ``ComposeLogFollow`` process lifecycle."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from raft.adapters.docker.compose_log_follow import ComposeLogFollow
from raft.adapters.shell import Shell

from ...base import RaftTestCase


class TestComposeLogFollow(RaftTestCase):
    def _follow(self) -> ComposeLogFollow:
        return ComposeLogFollow(Shell(self.tmp_path))

    def test_iter_lines_empty_services_yields_nothing(self) -> None:
        follow = self._follow()
        with patch.object(follow.sh, "popen") as popen:
            assert list(follow.iter_lines()) == []
        popen.assert_not_called()

    def test_iter_lines_closes_stdout(self) -> None:
        follow = self._follow()
        stdout = MagicMock()
        stdout.__iter__.return_value = iter(["z\n"])
        proc = MagicMock()
        proc.stdout = stdout
        proc.poll.return_value = 0
        with patch.object(follow.sh, "popen", return_value=proc):
            assert list(follow.iter_lines("app")) == ["z"]
        stdout.close.assert_called_once()

    def test_iter_lines_stops_process_on_close(self) -> None:
        follow = self._follow()
        proc = MagicMock()
        proc.stdout = iter(["one\n"])
        proc.poll.return_value = None
        proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="x", timeout=2), 0]
        with patch.object(follow.sh, "popen", return_value=proc):
            assert list(follow.iter_lines("app", tail=3)) == ["one"]
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()

    def test_iter_lines_none_stdout(self) -> None:
        follow = self._follow()
        proc = MagicMock()
        proc.stdout = None
        proc.poll.return_value = 0
        with patch.object(follow.sh, "popen", return_value=proc):
            assert list(follow.iter_lines("app")) == []
