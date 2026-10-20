"""Dashboard OAuth nginx, proxy cfg, secrets ops (PII-safe fixtures)."""

from pathlib import Path
from typing import Optional

import pytest

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
    DashboardOAuthConfig,
)
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.oauth_ops import DashboardOAuthOps
from raft.core.lifecycle.dashboard.oauth_proxy_cfg import DashboardOAuthProxyCfg
from raft.core.lifecycle.dashboard.proxy_nginx import DashboardProxyNginx
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.dashboard.oauth_test_helpers import seed_oauth_secrets


class TestDashboardOAuth(RaftTestCase):
    def test_nginx_oauth_gates_spa(self) -> None:
        text = DashboardProxyNginx().render(
            self._oauth_cfg(), listen=8787, app_port=18787
        )
        assert "auth_request /_raft_dashboard_auth" in text
        assert "/oauth2/auth" in text
        assert "location /oauth2/" in text
        assert "location = /unauthorized" in text
        assert "return 302 /oauth2/start" in text
        assert "X-Raft-Identity" in text
        assert "X-Forwarded-Proto $raft_fwd_proto" in text
        assert "location = /api/update" in text
        assert "proxy_read_timeout 600s" in text

    def test_proxy_cfg_google_and_oidc(self) -> None:
        google = DashboardOAuthProxyCfg().render(self._oauth_cfg())
        assert 'provider = "google"' in google
        assert "/raft/host/secrets/dashboard/oauth-allowlist.txt" in google
        oidc = DashboardOAuthProxyCfg().render(
            self._oauth_cfg(provider="oidc", issuer="https://login.example.com/")
        )
        assert 'provider = "oidc"' in oidc
        assert "login.example.com" in oidc

    def test_proxy_cfg_rejects_bad_provider_and_oidc_issuer(self) -> None:
        with pytest.raises(OperatorError, match="unsupported"):
            DashboardOAuthProxyCfg()._provider_lines("nope", None)
        with pytest.raises(OperatorError, match="issuerUrl"):
            DashboardOAuthProxyCfg().render(
                self._oauth_cfg(provider="oidc", issuer=None)
            )

    def test_ops_init_allowlist_and_enable(self) -> None:
        home = Path(self.tmp_path)
        seed_oauth_secrets(home)
        writer = DashboardSettingsWriter(home)
        writer.enable(
            public_host="ops.example.com",
            tls="acme",
            auth_mode="oauth",
        )
        snap = writer.status_public()
        assert snap["auth"]["mode"] == "oauth"
        assert snap["auth"]["oauth"]["secretsReady"] is True
        assert snap["auth"]["oauth"]["hasAllowlist"] is True

    def test_ops_require_ready_fails_without_secrets(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="oauth.env"):
            DashboardOAuthOps(home).require_ready(self._oauth_cfg())

    @staticmethod
    def _oauth_cfg(
        *, provider: str = "google", issuer: Optional[str] = None
    ) -> DashboardConfig:
        return DashboardConfig(
            public_host="ops.example.com",
            tls="acme",
            auth=DashboardAuthConfig(
                mode="oauth",
                oauth=DashboardOAuthConfig(provider=provider, issuer_url=issuer),
            ),
        )
