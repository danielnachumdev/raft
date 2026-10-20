"""HostDockerUpdate builds a host-targeted docker run argv."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.update import DEFAULT_HOST_UPDATE_IMAGE, HostDockerUpdate
from raft.core.observe.ops.update.install_cmd import InstallCmd


class TestHostDockerUpdate:
    def test_argv_user_home_and_image(self) -> None:
        args = self._argv(ref="main")
        assert args[:3] == ["docker", "run", "--rm"]
        assert "--user" in args and "1000:1000" in args
        assert "HOME=/home/demo" in args
        assert "/home/demo:/home/demo" in args
        assert args[args.index("-w") + 1] == "/home/demo"
        assert "example.test/curl-bash:1" in args

    def test_argv_path_and_pipefail_script(self) -> None:
        args = self._argv(ref="main")
        path_env = next(a for a in args if a.startswith("PATH="))
        assert path_env.startswith("PATH=/home/demo/.local/bin:")
        script = args[args.index("bash") + 2]
        assert "set -euo pipefail" in script
        assert "RAFT_INSTALL_QUIET=1" in script
        assert "RAFT_REF=main" in script
        assert args[-1] == "https://example.test/install.sh"

    def test_argv_default_image_and_omits_ref(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_HOST_UPDATE_IMAGE", raising=False)
        upd = HostDockerUpdate(
            MagicMock(), host_home="/home/demo", uid=1, gid=1
        )
        args = upd.argv("https://example.test/install.sh", None)
        assert DEFAULT_HOST_UPDATE_IMAGE in args
        script = args[args.index("bash") + 2]
        assert "RAFT_REF=" not in script
        assert script == InstallCmd.pipeline_script(None)

    def test_argv_prefers_raft_host_uid_gid_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_HOST_UID", "1001")
        monkeypatch.setenv("RAFT_HOST_GID", "1002")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.delenv("RAFT_HOST_UPDATE_IMAGE", raising=False)
        upd = HostDockerUpdate(MagicMock())
        args = upd.argv("https://example.test/install.sh", None)
        assert "1001:1002" in args

    def test_run_wraps_shell_failure(self) -> None:
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("install.sh: git is required")
        upd = HostDockerUpdate(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        with pytest.raises(OperatorError, match="git is required"):
            upd.run("https://example.test/install.sh", None)
        shell.run.assert_called_once()
        assert shell.run.call_args.kwargs.get("timeout") == 600.0
        assert shell.run.call_args.kwargs.get("capture") is True

    def test_run_succeeds(self) -> None:
        shell = MagicMock()
        upd = HostDockerUpdate(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        upd.run("https://example.test/install.sh", "v0.14.2")
        shell.run.assert_called_once()

    def test_resolve_id_falls_back_when_env_not_digit(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_HOST_UID", "not-a-number")
        monkeypatch.delenv("RAFT_HOST_GID", raising=False)
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(
            "raft.core.observe.ops.update.host_docker.os.getuid", lambda: 42
        )
        monkeypatch.setattr(
            "raft.core.observe.ops.update.host_docker.os.getgid", lambda: 43
        )
        upd = HostDockerUpdate(MagicMock())
        args = upd.argv("https://example.test/install.sh", None)
        assert "42:43" in args

    def test_default_image_includes_scm_tools(self) -> None:
        assert "bookworm-scm" in DEFAULT_HOST_UPDATE_IMAGE
        assert "bookworm-curl" not in DEFAULT_HOST_UPDATE_IMAGE

    def test_failure_message_prefers_stderr(self) -> None:
        exc = RuntimeError("ignored")
        exc.stderr = "line1\ninstall.sh: git is required\n"
        msg = HostDockerUpdate._failure_message(exc)
        assert "git is required" in msg
        assert "ignored" not in msg

    def test_failure_message_uses_output_when_no_stderr(self) -> None:
        exc = RuntimeError("ignored")
        exc.stderr = None
        exc.output = "docker: pull failed\n"
        msg = HostDockerUpdate._failure_message(exc)
        assert "pull failed" in msg

    def test_failure_message_ignores_non_str_output(self) -> None:
        exc = RuntimeError("fallback-msg")
        exc.stderr = None
        exc.output = 1
        msg = HostDockerUpdate._failure_message(exc)
        assert "fallback-msg" in msg

    def test_failure_message_unknown_when_empty(self) -> None:
        msg = HostDockerUpdate._failure_message(RuntimeError("   "))
        assert "unknown error" in msg

    @staticmethod
    def _argv(*, ref: str | None) -> list[str]:
        upd = HostDockerUpdate(
            MagicMock(),
            host_home="/home/demo",
            uid=1000,
            gid=1000,
            image="example.test/curl-bash:1",
        )
        return upd.argv("https://example.test/install.sh", ref)
