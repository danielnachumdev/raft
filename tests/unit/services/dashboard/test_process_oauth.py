"""oauth2-proxy sidecar helpers for DashboardProcess."""

import os
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.errors.cta import OperatorError
from raft.services.dashboard.process_oauth import DashboardOAuthProxyProcess
from tests.unit.base import RaftTestCase

_DEMO_ENV = {
    "OAUTH2_PROXY_CLIENT_ID": "demo",
    "OAUTH2_PROXY_CLIENT_SECRET": "secret",
    "OAUTH2_PROXY_COOKIE_SECRET": "x" * 32,
    "OAUTH2_PROXY_REDIRECT_URL": "https://ops.example.com/oauth2/callback",
}


class TestDashboardOAuthProxyProcess(RaftTestCase):
    def test_start_writes_cfg_and_spawns(self) -> None:
        cfg = DashboardConfig(auth=DashboardAuthConfig(mode="oauth"))
        conf = Path(self.tmp_path) / "oauth.cfg"
        proc = MagicMock()
        with patch.dict(os.environ, _DEMO_ENV, clear=False):
            with patch.object(
                DashboardOAuthProxyProcess, "_binary", return_value="/bin/x"
            ):
                with patch.object(DashboardOAuthProxyProcess, "_wait_ping"):
                    with patch(
                        "raft.services.dashboard.process_oauth.subprocess.Popen",
                        return_value=proc,
                    ) as popen:
                        with patch(
                            "raft.services.dashboard.process_oauth._CFG", conf
                        ):
                            assert DashboardOAuthProxyProcess().start(cfg) is proc
        assert "provider" in conf.read_text(encoding="utf-8")
        assert popen.call_args[0][0][0] == "oauth2-proxy"

    def test_require_env_and_binary(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(OperatorError, match="missing env"):
                DashboardOAuthProxyProcess._require_env()
        with patch.object(DashboardOAuthProxyProcess, "_binary", return_value=None):
            with pytest.raises(OperatorError, match="binary missing"):
                DashboardOAuthProxyProcess().start(
                    DashboardConfig(auth=DashboardAuthConfig(mode="oauth"))
                )

    def test_binary_which(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/oauth2-proxy"):
            assert DashboardOAuthProxyProcess._binary() == "/usr/bin/oauth2-proxy"

    def test_wait_ping_ok_and_timeout(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            with patch(
                "raft.services.dashboard.process_oauth.OAUTH_PROXY_PORT", port
            ):
                DashboardOAuthProxyProcess._wait_ping(timeout=1.0)
        with patch("raft.services.dashboard.process_oauth.OAUTH_PROXY_PORT", 1):
            with pytest.raises(RuntimeError, match="did not listen"):
                DashboardOAuthProxyProcess._wait_ping(timeout=0.05)
