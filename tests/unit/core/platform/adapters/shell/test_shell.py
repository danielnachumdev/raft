"""Shell adapter (subprocess mocked)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from raft.core.platform.adapters import Shell
from raft.core.platform.adapters.shell.active_child import ActiveShellChild

from tests.unit.base import RaftTestCase


def _popen_done(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> MagicMock:
    proc = MagicMock()
    proc.pid = 4242
    proc.returncode = returncode
    proc.poll.return_value = returncode
    proc.communicate.return_value = (stdout, stderr)
    return proc


class TestShell(RaftTestCase):
    @pytest.fixture(autouse=True)
    def _shell_setup(self, _raft_base) -> None:
        self.shell = Shell(self.tmp_path)
        ActiveShellChild._current = None

    def test_run_success_no_capture(self) -> None:
        proc = _popen_done()
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=proc,
        ) as popen:
            result = self.shell.run(["true"])
        popen.assert_called_once()
        assert popen.call_args.kwargs["cwd"] == self.tmp_path
        assert popen.call_args.kwargs["start_new_session"] is True
        env = popen.call_args.kwargs["env"]
        assert "RAFT_HOST_UID" in env and "RAFT_HOST_GID" in env
        assert "RAFT_DOCKER_GID" in env
        assert "RAFT_HOST_HOME" in env
        assert "RAFT_HOST_DOCKER_BIN" in env
        assert "RAFT_HOST_DOCKER_PLUGIN_DIR" in env
        assert result.returncode == 0

    def test_docker_socket_gid_from_stat(self) -> None:
        st = MagicMock(st_gid=988)
        with patch("raft.core.platform.adapters.shell.shell.os.stat", return_value=st) as stat:
            assert Shell._docker_socket_gid() == "988"
        stat.assert_called_once_with("/var/run/docker.sock")

    def test_host_docker_bin_prefers_which(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.shutil.which",
            return_value="/opt/docker",
        ):
            assert Shell._host_docker_bin() == "/opt/docker"

    def test_host_docker_bin_fallback(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.shutil.which",
            return_value=None,
        ):
            assert Shell._host_docker_bin() == "/usr/bin/docker"

    def test_host_docker_plugin_dir_prefers_existing(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.os.path.isdir",
            side_effect=lambda p: p.endswith("/usr/local/lib/docker/cli-plugins"),
        ):
            assert Shell._host_docker_plugin_dir() == (
                "/usr/local/lib/docker/cli-plugins"
            )

    def test_host_docker_plugin_dir_fallback(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.os.path.isdir",
            return_value=False,
        ):
            assert Shell._host_docker_plugin_dir() == (
                "/usr/libexec/docker/cli-plugins"
            )

    def test_docker_socket_gid_missing_socket(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.os.stat",
            side_effect=FileNotFoundError,
        ):
            assert Shell._docker_socket_gid() == "0"

    def test_run_check_raises_with_captured_detail(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=_popen_done(returncode=7, stdout="out", stderr="err detail"),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=True)
        assert "err detail" in (exc.value.stderr or "")

    def test_run_check_raises_uses_stdout_when_stderr_empty(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=_popen_done(returncode=2, stdout="stdout only", stderr=""),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=True)
        assert "stdout only" in (exc.value.stderr or "")

    def test_run_check_raises_empty_streams(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=_popen_done(returncode=2),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=True)
        assert exc.value.returncode == 2

    def test_run_check_raises_without_capture(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=_popen_done(returncode=1, stdout="ignored", stderr="ignored"),
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                self.shell.run(["false"], check=True, capture=False)
        assert exc.value.returncode == 1
        assert (exc.value.stderr or "") == "ignored"

    def test_run_no_check_returns_failure(self) -> None:
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=_popen_done(returncode=1),
        ):
            assert self.shell.run(["false"], check=False).returncode == 1

    def test_run_timeout_check_false_returns_124(self) -> None:
        proc = _popen_done()
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd=["sleep"], timeout=1.5, output=b"partial", stderr=b"err"
        )
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=proc,
        ):
            with patch.object(ActiveShellChild, "terminate") as terminate:
                result = self.shell.run(
                    ["sleep", "9"], check=False, capture=True, timeout=1.5
                )
        terminate.assert_called_once_with(proc)
        assert result.returncode == 124
        assert result.stdout == "partial"
        assert result.stderr == "err"

    def test_timeout_stream_none_and_str(self) -> None:
        assert Shell._timeout_stream(None) == ""
        assert Shell._timeout_stream(12) == "12"

    def test_run_timeout_empty_streams_message(self) -> None:
        proc = _popen_done()
        proc.communicate.side_effect = subprocess.TimeoutExpired(cmd=["sleep"], timeout=0.2)
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=proc,
        ):
            with patch.object(ActiveShellChild, "terminate"):
                result = self.shell.run(["sleep", "9"], check=False, timeout=0.2)
        assert result.returncode == 124
        assert "timed out after 0.2s" in (result.stderr or "")

    def test_run_timeout_check_true_raises(self) -> None:
        proc = _popen_done()
        proc.communicate.side_effect = subprocess.TimeoutExpired(cmd=["sleep"], timeout=0.1)
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=proc,
        ):
            with patch.object(ActiveShellChild, "terminate"):
                with pytest.raises(subprocess.TimeoutExpired):
                    self.shell.run(["sleep", "9"], check=True, timeout=0.1)

    def test_run_keyboard_interrupt_terminates_child(self) -> None:
        proc = _popen_done()
        proc.communicate.side_effect = KeyboardInterrupt
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=proc,
        ):
            with patch.object(ActiveShellChild, "terminate") as terminate:
                with pytest.raises(KeyboardInterrupt):
                    self.shell.run(["sleep", "9"])
        terminate.assert_called_once_with(proc)
        assert ActiveShellChild._current is None

    def test_compose_docker_git_wrappers(self) -> None:
        with patch.object(self.shell, "run", return_value=MagicMock()) as run:
            self.shell.compose("ps")
            self.shell.docker("ps")
            self.shell.git("status", cwd=self.tmp_path)
        assert run.call_args_list[0].args[0][:2] == ["docker", "compose"]
        assert run.call_args_list[1].args[0][:1] == ["docker"]
        assert run.call_args_list[2].args[0][:1] == ["git"]

    def test_popen_pipes_stdout(self) -> None:
        proc = MagicMock()
        with patch(
            "raft.core.platform.adapters.shell.shell.subprocess.Popen",
            return_value=proc,
        ) as popen:
            assert self.shell.popen(["echo", "hi"]) is proc
        popen.assert_called_once()
        kwargs = popen.call_args.kwargs
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.STDOUT
        assert kwargs["text"] is True
        assert kwargs["cwd"] == self.tmp_path
        assert kwargs["start_new_session"] is True
        assert ActiveShellChild._current is proc
