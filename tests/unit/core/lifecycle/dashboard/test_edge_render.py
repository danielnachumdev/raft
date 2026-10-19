"""Dashboard edge render emits auth_request for external auth."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.lifecycle.dashboard.edge_render import DashboardEdgeRender
from tests.unit.base import RaftTestCase


class TestDashboardEdgeRender(RaftTestCase):
    def test_external_emits_auth_request(self) -> None:
        cfg = DashboardConfig(
            enabled=True,
            port=8787,
            public_host="ops.example.com",
            tls="off",
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
            ),
        )
        frag = DashboardEdgeRender().contribute(
            cfg,
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        text = "\n".join(frag.gate_http)
        assert "auth_request /_raft_dashboard_auth" in text
        assert "http://auth.demo.example/verify" in text
        assert "raft-dashboard-http.conf" in frag.upstreams

    def test_disabled_emits_nothing(self) -> None:
        frag = DashboardEdgeRender().contribute(
            DashboardConfig(),
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        assert frag.upstreams == {}
        assert frag.gate_http == []
