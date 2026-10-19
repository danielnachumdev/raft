"""In-container dashboard nginx auth proxy config."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.lifecycle.dashboard.proxy_nginx import DashboardProxyNginx
from tests.unit.base import RaftTestCase


class TestDashboardProxyNginx(RaftTestCase):
    def test_none_proxies_open(self) -> None:
        text = DashboardProxyNginx().render(
            DashboardConfig(), listen=8787, app_port=18787
        )
        assert "listen 8787" in text
        assert "auth_request" not in text
        assert "proxy_pass http://127.0.0.1:18787" in text

    def test_password_gates_spa(self) -> None:
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(mode="password", password_hash="x")
        )
        text = DashboardProxyNginx().render(
            cfg,
            listen=8787,
            app_port=18787,
            login_html=Path("/opt/dashboard/login.html"),
        )
        assert "auth_request /_raft_dashboard_auth" in text
        assert "server_tokens off" in text
        assert "absolute_redirect off" in text
        assert "port_in_redirect off" in text
        assert "location = /login" in text
        assert "location = /api/dashboard/login" in text
        assert "location = /api/dashboard/logout" in text
        assert "/api/dashboard/auth" in text
        assert "return 302 /login" in text

    def test_external_gates_spa(self) -> None:
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
            )
        )
        text = DashboardProxyNginx().render(cfg, listen=8787, app_port=18787)
        assert "proxy_pass http://auth.demo.example/verify" in text
        assert "return 302 https://auth.demo.example/sign-in" in text
        assert "X-Raft-Identity" in text
