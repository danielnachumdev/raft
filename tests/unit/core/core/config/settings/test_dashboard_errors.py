"""Additional dashboard settings parser error branches."""

import pytest

from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.errors.cta import OperatorError
from tests.unit.base import RaftTestCase


class TestDashboardParserErrors(RaftTestCase):
    def test_not_mapping(self) -> None:
        with pytest.raises(OperatorError, match="must be a mapping"):
            DashboardSettingsParser().parse([])

    def test_bad_tls(self) -> None:
        with pytest.raises(OperatorError, match="dashboard.tls"):
            DashboardSettingsParser().parse({"tls": "dns"})

    def test_bad_auth_mode(self) -> None:
        with pytest.raises(OperatorError, match="auth.mode"):
            DashboardSettingsParser().parse({"auth": {"mode": "ldap"}})

    def test_auth_not_mapping(self) -> None:
        with pytest.raises(OperatorError, match="dashboard.auth must be a mapping"):
            DashboardSettingsParser().parse({"auth": "password"})

    def test_identity_header_default(self) -> None:
        cfg = DashboardSettingsParser().parse({"auth": {"mode": "none"}})
        assert cfg.auth.identity_header == "X-Raft-Identity"

    def test_users_must_be_list(self) -> None:
        with pytest.raises(OperatorError, match="users must be a list"):
            DashboardSettingsParser().parse(
                {"auth": {"mode": "password", "users": {}}}
            )

    def test_user_entry_errors(self) -> None:
        with pytest.raises(OperatorError, match="must be a mapping"):
            DashboardSettingsParser().parse(
                {"auth": {"mode": "password", "users": ["admin"]}}
            )
        with pytest.raises(OperatorError, match="requires username"):
            DashboardSettingsParser().parse(
                {
                    "auth": {
                        "mode": "password",
                        "users": [{"username": "", "passwordHash": "x"}],
                    }
                }
            )

    def test_users_parse_ok(self) -> None:
        cfg = DashboardSettingsParser().parse(
            {
                "auth": {
                    "mode": "password",
                    "users": [
                        {"username": "Ops", "passwordHash": "pbkdf2$demo"},
                    ],
                }
            }
        )
        assert cfg.auth.users[0].username == "ops"
