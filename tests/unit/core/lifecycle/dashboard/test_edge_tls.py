"""Dashboard edge TLS / external-origin paths."""

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

    def test_external_origin_tls(self) -> None:
        frag = DashboardEdgeRender().contribute(
            self._cfg(),
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        assert "raft-dashboard.conf" in frag.gate_tls
        assert "auth_request" in frag.gate_tls["raft-dashboard.conf"]
        assert "ssl_certificate" in frag.gate_tls["raft-dashboard.conf"]

    def test_external_origin_needs_https(self) -> None:
        with pytest.raises(OperatorError, match="edge.https"):
            DashboardEdgeRender().contribute(
                self._cfg(),
                edge=EdgeConfig(http=80, https=None),
                data_home=Path(self.tmp_path),
            )

    def test_external_tls_off_needs_http(self) -> None:
        with pytest.raises(OperatorError, match="edge.http"):
            DashboardEdgeRender().contribute(
                self._cfg(tls="off"),
                edge=EdgeConfig(http=None, https=443),
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

    def test_password_mode_uses_tls_edge(self) -> None:
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
        assert "raft-dashboard.conf" in frag.gate_tls
        assert "auth_request" not in frag.gate_tls["raft-dashboard.conf"]
