"""HostOneshot builds sync / detached docker run argv."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.adapters.docker import (
    DEFAULT_HOST_ONESHOT_IMAGE,
    HostOneshot,
)
from raft.core.platform.adapters.docker import host_oneshot_ids as ids_mod
from raft.core.platform.adapters.docker import host_oneshot_mounts as mounts_mod


class TestHostOneshot:
    def test_run_argv_without_docker(self) -> None:
        args = self._argv(with_docker=False, detach=False)
        assert args[:3] == ["docker", "run", "--rm"]
        assert "-d" not in args
        assert "--group-add" not in args
        assert "/var/run/docker.sock" not in " ".join(args)
        assert "1000:1000" in args
        assert "HOME=/home/demo" in args
        assert args[-2:] == ["raft", "version"]

    def test_start_argv_with_docker(self, monkeypatch) -> None:
        monkeypatch.setattr(
            mounts_mod.shutil, "which", lambda _n: "/usr/bin/docker"
        )
        monkeypatch.setattr(
            mounts_mod.os.path, "isfile", lambda _p: True
        )
        monkeypatch.setattr(
            mounts_mod.os.path, "isdir", lambda _p: False
        )
        args = self._argv(with_docker=True, detach=True)
        assert args[:4] == ["docker", "run", "-d", "--rm"]
        assert "--group-add" in args and "988" in args
        assert "/var/run/docker.sock:/var/run/docker.sock" in args
        assert "/usr/bin/docker:/usr/bin/docker:ro" in args

    def test_run_calls_shell_with_timeout(self) -> None:
        shell = MagicMock()
        oneshot = HostOneshot(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        oneshot.run(["echo", "ok"], timeout=12.5, with_docker=False)
        shell.run.assert_called_once()
        assert shell.run.call_args.kwargs.get("timeout") == 12.5
        assert shell.run.call_args.kwargs.get("capture") is True

    def test_start_returns_container_id(self) -> None:
        shell = MagicMock()
        shell.run.return_value = MagicMock(stdout="abc123def\n")
        oneshot = HostOneshot(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        job_id = oneshot.start(["raft", "redeploy", "dashboard"])
        assert job_id == "abc123def"
        cmd = shell.run.call_args.args[0]
        assert cmd[:4] == ["docker", "run", "-d", "--rm"]
        assert cmd[-3:] == ["raft", "redeploy", "dashboard"]

    def test_start_refuses_empty_id(self) -> None:
        shell = MagicMock()
        shell.run.return_value = MagicMock(stdout="\n")
        oneshot = HostOneshot(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        with pytest.raises(OperatorError, match="no container id"):
            oneshot.start(["raft", "version"])

    def test_run_wraps_shell_failure(self) -> None:
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("pull failed")
        oneshot = HostOneshot(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        with pytest.raises(OperatorError, match="pull failed"):
            oneshot.run(["true"], timeout=1.0)

    def test_default_image_and_env_ids(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_HOST_UID", "1001")
        monkeypatch.setenv("RAFT_HOST_GID", "1002")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.delenv("RAFT_HOST_UPDATE_IMAGE", raising=False)
        oneshot = HostOneshot(MagicMock())
        args = oneshot.docker_argv(["true"], with_docker=False, detach=False)
        assert "1001:1002" in args
        assert DEFAULT_HOST_ONESHOT_IMAGE in args

    def test_resolve_id_falls_back_when_env_not_digit(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_HOST_UID", "not-a-number")
        monkeypatch.delenv("RAFT_HOST_GID", raising=False)
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(ids_mod.os, "getuid", lambda: 42)
        monkeypatch.setattr(ids_mod.os, "getgid", lambda: 43)
        oneshot = HostOneshot(MagicMock())
        args = oneshot.docker_argv(["true"], with_docker=False, detach=False)
        assert "42:43" in args

    def test_failure_message_prefers_stderr(self) -> None:
        exc = RuntimeError("ignored")
        exc.stderr = "line1\nbad pull\n"
        msg = HostOneshot._failure_message(exc)
        assert "bad pull" in msg
        assert "ignored" not in msg

    def test_failure_message_uses_output(self) -> None:
        exc = RuntimeError("ignored")
        exc.stderr = None
        exc.output = "docker: pull failed\n"
        assert "pull failed" in HostOneshot._failure_message(exc)

    def test_failure_message_unknown_when_empty(self) -> None:
        assert "unknown error" in HostOneshot._failure_message(RuntimeError("   "))

    def test_failure_message_ignores_non_str_output(self) -> None:
        exc = RuntimeError("fallback-msg")
        exc.stderr = None
        exc.output = 1
        assert "fallback-msg" in HostOneshot._failure_message(exc)

    def test_parse_container_id_ignores_non_str(self) -> None:
        with pytest.raises(OperatorError, match="no container id"):
            HostOneshot._parse_container_id(None)

    def test_start_wraps_shell_failure(self) -> None:
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("cannot start")
        oneshot = HostOneshot(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        with pytest.raises(OperatorError, match="cannot start"):
            oneshot.start(["raft", "version"])

    def test_plugin_dirs_mounted_when_present(self, monkeypatch) -> None:
        monkeypatch.setattr(mounts_mod.shutil, "which", lambda _n: None)
        monkeypatch.setattr(
            mounts_mod.os.path,
            "isdir",
            lambda p: p == "/usr/libexec/docker/cli-plugins",
        )
        args = self._argv(with_docker=True, detach=False)
        assert (
            "/usr/libexec/docker/cli-plugins:/usr/libexec/docker/cli-plugins:ro"
            in args
        )

    def test_docker_gid_from_sock_stat(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_DOCKER_GID", raising=False)
        real_stat = ids_mod.os.stat

        def fake_stat(path, *args, **kwargs):
            if path == "/var/run/docker.sock":
                return MagicMock(st_gid=777)
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(ids_mod.os, "stat", fake_stat)
        oneshot = HostOneshot(
            MagicMock(), host_home="/home/demo", uid=1, gid=1, image="img"
        )
        args = oneshot.docker_argv(["true"], with_docker=True, detach=False)
        assert "777" in args

    def test_docker_gid_fallback_when_sock_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_DOCKER_GID", raising=False)
        real_stat = ids_mod.os.stat

        def fake_stat(path, *args, **kwargs):
            if path == "/var/run/docker.sock":
                raise OSError("missing")
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(ids_mod.os, "stat", fake_stat)
        oneshot = HostOneshot(
            MagicMock(), host_home="/home/demo", uid=1, gid=1, image="img"
        )
        args = oneshot.docker_argv(["true"], with_docker=True, detach=False)
        assert "--group-add" in args and "0" in args

    def test_explicit_docker_gid_and_image(self) -> None:
        oneshot = HostOneshot(
            MagicMock(),
            host_home="/home/demo",
            uid=1,
            gid=1,
            docker_gid=42,
            image="custom:1",
        )
        args = oneshot.docker_argv(["true"], with_docker=True, detach=False)
        assert "42" in args
        assert "custom:1" in args

    def test_docker_gid_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DOCKER_GID", "555")
        oneshot = HostOneshot(
            MagicMock(), host_home="/home/demo", uid=1, gid=1, image="img"
        )
        args = oneshot.docker_argv(["true"], with_docker=True, detach=False)
        assert "555" in args

    @staticmethod
    def _argv(*, with_docker: bool, detach: bool) -> list[str]:
        oneshot = HostOneshot(
            MagicMock(),
            host_home="/home/demo",
            uid=1000,
            gid=1000,
            docker_gid=988,
            image="example.test/curl-bash:1",
        )
        return oneshot.docker_argv(
            ["raft", "version"], with_docker=with_docker, detach=detach
        )
