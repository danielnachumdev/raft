"""Coverage gaps for dashboard OAuth helpers."""

from pathlib import Path

import pytest

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
    DashboardOAuthConfig,
)
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.oauth_allowlist import DashboardOAuthAllowlist
from raft.core.lifecycle.dashboard.oauth_env import DashboardOAuthEnv
from raft.core.lifecycle.dashboard.oauth_ops import DashboardOAuthOps
from raft.core.lifecycle.dashboard.oauth_paths import DashboardOAuthPaths
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.dashboard.oauth_test_helpers import seed_oauth_secrets


class TestDashboardOAuthGaps(RaftTestCase):
    def test_allowlist_edges(self) -> None:
        home = Path(self.tmp_path)
        al = DashboardOAuthAllowlist(home)
        assert al.read() == []
        first = al.ensure()
        assert al.ensure() == first
        with pytest.raises(OperatorError, match="not found"):
            al.set_from_file(home / "missing.txt")
        with pytest.raises(OperatorError, match="non-empty"):
            al.add("# comment")
        al.add("ops@example.com")
        assert al.add("OPS@example.com")["count"] == 1
        assert al.write([])["count"] == 0

    def test_env_redirect_path_and_http(self) -> None:
        cfg = DashboardConfig(
            public_host="ops.example.com",
            tls="off",
            auth=DashboardAuthConfig(
                mode="oauth",
                oauth=DashboardOAuthConfig(redirect_path="oauth2/callback"),
            ),
        )
        url = DashboardOAuthEnv.redirect_url(cfg)
        assert url.startswith("http://")
        assert url.endswith("/oauth2/callback")

    def test_env_parse_skips_blank_comment_and_bare_keys(self) -> None:
        parsed = DashboardOAuthEnv._parse(
            "\n# note\nNOT_AN_ASSIGNMENT\nA=1\nB=\"two\"\nC='three'\n"
        )
        assert parsed == {"A": "1", "B": "two", "C": "three"}

    def test_paths_absolute_allowlist(self) -> None:
        home = Path(self.tmp_path)
        abs_path = home / "custom.txt"
        assert DashboardOAuthPaths(home).allowlist_file(str(abs_path)) == abs_path

    def test_ops_bad_provider(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="provider must be"):
            DashboardOAuthOps(home).init(provider="nope")

    def test_ops_allowlist_add(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        ops = DashboardOAuthOps(home)
        result = ops.allowlist_add("ops@example.com")
        assert result["count"] == 1
        assert "ops@example.com" in DashboardOAuthAllowlist(home).read()

    def test_writer_oauth_provider_only(self) -> None:
        home = Path(self.tmp_path)
        seed_oauth_secrets(home)
        writer = DashboardSettingsWriter(home)
        writer.enable(
            public_host="ops.example.com",
            tls="acme",
            auth_mode="oauth",
            oauth_provider="google",
        )
        assert writer.load().auth.oauth.provider == "google"

    def test_writer_oauth_issuer_then_oidc(self) -> None:
        home = Path(self.tmp_path)
        seed_oauth_secrets(home)
        writer = DashboardSettingsWriter(home)
        writer.enable(
            public_host="ops.example.com",
            tls="acme",
            auth_mode="oauth",
        )
        writer.enable(oauth_issuer_url="https://login.example.com/")
        writer.enable(
            oauth_provider="oidc",
            oauth_issuer_url="https://login.example.com/",
        )
        cfg = writer.load()
        assert cfg.auth.oauth.provider == "oidc"
        assert cfg.auth.oauth.issuer_url == "https://login.example.com/"
