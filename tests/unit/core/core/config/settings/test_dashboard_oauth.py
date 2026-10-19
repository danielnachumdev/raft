"""dashboard.auth.oauth settings parser coverage."""

import pytest

from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.errors.cta import OperatorError
from tests.unit.base import RaftTestCase


class TestDashboardOAuthSection(RaftTestCase):
    def test_oauth_google_ok(self) -> None:
        cfg = DashboardSettingsParser().parse(
            {
                "publicHost": "ops.example.com",
                "tls": "acme",
                "auth": {"mode": "oauth", "oauth": {"provider": "google"}},
            }
        )
        assert cfg.auth.mode == "oauth"
        assert cfg.auth.oauth.provider == "google"
        assert cfg.uses_identity_header() is True

    def test_oauth_oidc_requires_issuer(self) -> None:
        with pytest.raises(OperatorError, match="issuerUrl"):
            DashboardSettingsParser().parse(
                {
                    "publicHost": "ops.example.com",
                    "tls": "acme",
                    "auth": {"mode": "oauth", "oauth": {"provider": "oidc"}},
                }
            )

    def test_oauth_oidc_ok(self) -> None:
        cfg = DashboardSettingsParser().parse(
            {
                "publicHost": "ops.example.com",
                "tls": "acme",
                "auth": {
                    "mode": "oauth",
                    "oauth": {
                        "provider": "oidc",
                        "issuerUrl": "https://login.example.com/",
                    },
                },
            }
        )
        assert cfg.auth.oauth.issuer_url == "https://login.example.com/"

    def test_oauth_mapping_and_provider_errors(self) -> None:
        with pytest.raises(OperatorError, match="oauth must be a mapping"):
            DashboardSettingsParser().parse(
                {"auth": {"mode": "oauth", "oauth": ["nope"]}}
            )
        with pytest.raises(OperatorError, match="oauth.provider must be"):
            DashboardSettingsParser().parse(
                {"auth": {"mode": "oauth", "oauth": {"provider": "nope"}}}
            )
        defaults = DashboardSettingsParser().parse(
            {"auth": {"mode": "oauth", "oauth": {}}}
        )
        assert defaults.auth.oauth.provider == "google"
