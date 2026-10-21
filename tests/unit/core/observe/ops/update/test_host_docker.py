"""HostDockerUpdate builds install argv via shared HostOneshot."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.update import DEFAULT_HOST_UPDATE_IMAGE, HostDockerUpdate
from raft.core.observe.ops.update.install_cmd import InstallCmd
from raft.core.platform.adapters.docker import HostOneshot


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

    def test_run_uses_oneshot_without_docker(self) -> None:
        oneshot = MagicMock(spec=HostOneshot)
        upd = HostDockerUpdate(MagicMock(), oneshot=oneshot)
        upd.run("https://example.test/install.sh", "v0.14.2")
        oneshot.run.assert_called_once()
        kwargs = oneshot.run.call_args.kwargs
        assert kwargs.get("timeout") == 600.0
        assert kwargs.get("with_docker") is False
        inner = oneshot.run.call_args.args[0]
        assert inner[0] == "bash"
        assert inner[-1] == "https://example.test/install.sh"

    def test_run_wraps_oneshot_failure(self) -> None:
        oneshot = MagicMock(spec=HostOneshot)
        oneshot.run.side_effect = OperatorError(
            "host Docker one-shot failed: install.sh: git is required\nFix: …"
        )
        upd = HostDockerUpdate(MagicMock(), oneshot=oneshot)
        with pytest.raises(OperatorError, match="git is required") as exc:
            upd.run("https://example.test/install.sh", None)
        assert "Settings → Update" in str(exc.value)

    def test_default_image_includes_scm_tools(self) -> None:
        assert "bookworm-scm" in DEFAULT_HOST_UPDATE_IMAGE
        assert "bookworm-curl" not in DEFAULT_HOST_UPDATE_IMAGE

    def test_wrap_failure_strips_oneshot_prefix(self) -> None:
        msg = HostDockerUpdate._wrap_failure(
            "host Docker one-shot failed: pull failed\nFix: check Docker"
        )
        assert "raft update failed" in msg
        assert "pull failed" in msg
        assert msg.count("host Docker one-shot failed") == 0

    def test_wrap_failure_without_prefix(self) -> None:
        msg = HostDockerUpdate._wrap_failure("plain failure")
        assert "plain failure" in msg
        assert "raft update failed" in msg

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
