"""RBAC identity resolution from auth mode (#307)."""

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.rbac import (
    NONE_BOOTSTRAP_SUBJECT,
    PASSWORD_BOOTSTRAP_SUBJECT,
    RbacIdentity,
)
from tests.unit.base import RaftTestCase


class TestRbacIdentity(RaftTestCase):
    def test_oauth_header_normalized(self) -> None:
        cfg = DashboardConfig(
            auth=DashboardAuthConfig(mode="oauth", identity_header="X-Raft-Identity")
        )
        subject = RbacIdentity(cfg).from_headers(
            {"X-Raft-Identity": "Ops@Example.com"}
        )
        assert subject == "ops@example.com"

    def test_password_and_none_defaults(self) -> None:
        password = DashboardConfig(auth=DashboardAuthConfig(mode="password"))
        assert (
            RbacIdentity(password).from_headers({}) == PASSWORD_BOOTSTRAP_SUBJECT
        )
        none = DashboardConfig(auth=DashboardAuthConfig(mode="none"))
        assert RbacIdentity(none).from_headers({}) == NONE_BOOTSTRAP_SUBJECT
