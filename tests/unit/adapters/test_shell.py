"""Shell adapter (subprocess mocked)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from raft.adapters import Shell

from ..base import RaftTestCase, completed


class TestShell(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _shell_setup(self, _raft_base) -> None:
        self.shell = Shell(self.tmp_path)

    def test_run_success_no_capture(self) -> None:
        done = completed(returncode=0)
        done.stdout = None
        done.stderr = None
        with patch("raft.adapters.shell.subprocess.run", return_value=done) as run:
            assert self.shell.run(["true"]) is done
        run.assert_called_once()
        assert run.call_args.kwargs["cwd"] == self.tmp_path
        env = run.call_args.kwargs["env"]
        assert "RAFT_HOST_UID" in env and "RAFT_HOST_GID" in env
        assert "RAFT_DOCKER_GID" in env

    def test_docker_socket_gid_from_stat(self) -> None:
        st = MagicMock(st_gid=988)
        with patch("raft.adapters.shell.os.stat", return_value=st) as stat:
            assert Shell._docker_socket_gid() == "988"
        stat.assert_called_once_with("/var/run/docker.sock")

    def test_docker_socket_gid_missing_socket(self) -> None:
        with patch("raft.adapters.shell.os.stat", side_effect=FileNotFoundError):
            assert Shell._docker_socket_gid() == "0"

    def test_run_check_raises_with_captured_detail(self) -> None:
        with patch(
            "raft.adapters.shell.subprocess.run",
            return_value=completed(stdout="out", returncode=7, stderr="err detail"),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=True)
        assert "err detail" in (exc.value.stderr or "")

    def test_run_check_raises_uses_stdout_when_stderr_empty(self) -> None:
        with patch(
            "raft.adapters.shell.subprocess.run",
            return_value=completed(stdout="stdout only", returncode=2, stderr=""),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=True)
        assert "stdout only" in (exc.value.stderr or "")

    def test_run_check_raises_empty_streams(self) -> None:
        with patch(
            "raft.adapters.shell.subprocess.run",
            return_value=completed(returncode=2),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=True)
        assert exc.value.returncode == 2

    def test_run_check_raises_without_capture(self) -> None:
        with patch(
            "raft.adapters.shell.subprocess.run",
            return_value=completed(stdout="ignored", returncode=1, stderr="ignored"),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=False)
        assert exc.value.returncode == 1
        assert (exc.value.stderr or "") == "ignored"

    def test_run_no_check_returns_failure(self) -> None:
        with patch(
            "raft.adapters.shell.subprocess.run",
            return_value=completed(returncode=1),
        ):
            assert self.shell.run(["false"], check=False).returncode == 1

    def test_compose_docker_git_wrappers(self) -> None:
        with patch.object(self.shell, "run", return_value=MagicMock()) as run:
            self.shell.compose("ps")
            self.shell.docker("ps")
            self.shell.git("status", cwd=self.tmp_path)
        assert run.call_args_list[0].args[0][:2] == ["docker", "compose"]
        assert run.call_args_list[1].args[0][:1] == ["docker"]
        assert run.call_args_list[2].args[0][:1] == ["git"]
