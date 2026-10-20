"""Dashboard edge TLS paths (auth stays inside the dashboard container)."""

from pathlib import Path

import pytest

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.edge_render import DashboardEdgeRender
from tests.unit.base import RaftTestCase


class TestDashboardEdgeTls(RaftTestCase):
    def _cfg(self, **kwargs) -> DashboardConfig:
        base = dict(
            enabled=True,
            port=8787,
            public_host="ops.example.com",
            tls="origin",
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
            ),
        )
        base.update(kwargs)
        return DashboardConfig(**base)

    def test_origin_tls_no_gate_auth_request(self) -> None:
        frag = DashboardEdgeRender().contribute(
            self._cfg(),
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        text = frag.gate_tls["raft-dashboard.conf"]
        assert "ssl_certificate" in text
        assert "auth_request" not in text
        # Must exceed default gate 60s so Settings → Update can finish.
        assert "proxy_read_timeout 600s" in text
        assert "proxy_send_timeout 600s" in text
        assert "proxy_router.inc" not in text

    def test_origin_needs_https(self) -> None:
        with pytest.raises(OperatorError, match="edge.https"):
            DashboardEdgeRender().contribute(
                self._cfg(),
                edge=EdgeConfig(http=80, https=None),
                data_home=Path(self.tmp_path),
            )

    def test_password_public_needs_hash_on_render(self) -> None:
        cfg = DashboardConfig(
            enabled=True,
            public_host="ops.example.com",
            tls="off",
            auth=DashboardAuthConfig(mode="password"),
        )
        with pytest.raises(OperatorError, match="passwordHash"):
            DashboardEdgeRender().contribute(
                cfg,
                edge=EdgeConfig(http=80, https=443),
                data_home=Path(self.tmp_path),
            )

    def test_password_origin_tls_no_gate_auth_request(self) -> None:
        cfg = DashboardConfig(
            enabled=True,
            public_host="ops.example.com",
            tls="origin",
            auth=DashboardAuthConfig(mode="password", password_hash="x"),
        )
        frag = DashboardEdgeRender().contribute(
            cfg,
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        text = frag.gate_tls["raft-dashboard.conf"]
        assert "ssl_certificate" in text
        assert "auth_request" not in text
        assert "proxy_read_timeout 600s" in text
