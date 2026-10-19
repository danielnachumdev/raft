"""dashboard: settings section validation matrix."""

import pytest

from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.errors.cta import OperatorError
from tests.unit.base import RaftTestCase


class TestDashboardSection(RaftTestCase):
    def test_defaults(self) -> None:
        cfg = DashboardSettingsParser().parse(None)
        assert cfg.enabled is False
        assert cfg.port == 8787
        assert cfg.auth.mode == "none"

    def test_none_rejects_public_host(self) -> None:
        with pytest.raises(OperatorError, match="none cannot set publicHost"):
            DashboardSettingsParser().parse(
                {"publicHost": "ops.example.com", "auth": {"mode": "none"}}
            )

    def test_external_requires_urls(self) -> None:
        with pytest.raises(OperatorError, match="verifyUrl and signInUrl"):
            DashboardSettingsParser().parse(
                {
                    "publicHost": "ops.example.com",
                    "tls": "acme",
                    "auth": {"mode": "external"},
                }
            )

    def test_password_public_ok_without_hash(self) -> None:
        cfg = DashboardSettingsParser().parse(
            {
                "enabled": False,
                "publicHost": "ops.example.com",
                "tls": "acme",
                "auth": {"mode": "password"},
            }
        )
        assert cfg.requires_password_hash() is True
        assert cfg.auth.password_hash is None

    def test_external_ok(self) -> None:
        cfg = DashboardSettingsParser().parse(
            {
                "enabled": True,
                "publicHost": "ops.example.com",
                "tls": "acme",
                "auth": {
                    "mode": "external",
                    "verifyUrl": "http://auth.demo.example/verify",
                    "signInUrl": "https://auth.demo.example/sign-in",
                },
            }
        )
        assert cfg.auth.mode == "external"
        assert cfg.tls == "acme"
