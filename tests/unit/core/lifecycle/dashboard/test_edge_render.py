"""Dashboard edge render uses plain Host→upstream (auth is in-container)."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.lifecycle.dashboard.edge_render import DashboardEdgeRender
from tests.unit.base import RaftTestCase


class TestDashboardEdgeRender(RaftTestCase):
    def test_external_no_gate_auth(self) -> None:
        self._assert_plain_edge(
            DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
            )
        )

    def test_password_no_gate_auth(self) -> None:
        self._assert_plain_edge(
            DashboardAuthConfig(mode="password", password_hash="x")
        )

    def test_disabled_emits_nothing(self) -> None:
        frag = DashboardEdgeRender().contribute(
            DashboardConfig(),
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        assert frag.upstreams == {}
        assert frag.gate_http == []

    def _assert_plain_edge(self, auth: DashboardAuthConfig) -> None:
        cfg = DashboardConfig(
            enabled=True,
            port=8787,
            public_host="ops.example.com",
            tls="off",
            auth=auth,
        )
        frag = DashboardEdgeRender().contribute(
            cfg,
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        assert "raft-dashboard-http.conf" in frag.upstreams
        assert frag.gate_http == []
        assert "auth_request" not in str(frag.gate_tls)
        joined = "\n".join(frag.router_servers)
        assert "X-Forwarded-Proto $http_x_forwarded_proto" in joined
