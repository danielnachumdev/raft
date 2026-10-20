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

    def test_run_wraps_shell_failure(self) -> None:
        shell = MagicMock()
        shell.run.side_effect = RuntimeError("boom")
        upd = HostDockerUpdate(
            shell, host_home="/home/demo", uid=1, gid=1, image="img"
        )
        with pytest.raises(OperatorError, match="host Docker one-shot"):
            upd.run("https://example.test/install.sh", None)
        shell.run.assert_called_once()
        assert shell.run.call_args.kwargs.get("timeout") == 600.0

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
