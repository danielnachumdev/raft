"""Render emits gate holding/wake snippets for ``spec.scaling`` apps."""

from __future__ import annotations

import pytest

from raft.config.settings_types import EdgeConfig
from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.scaling_spec import ScalingSpec
from raft.models.stack import load_stack
from raft.services.render import StackRenderer
from raft.services.render.scaling_gate import ScalingGate

from ...base import RaftTestCase, write_applied_app

_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 120,
    "minUpSeconds": 30,
}


class TestScalingRender(RaftTestCase):
    def test_gate_http_includes_holding_and_wake(self) -> None:
        write_applied_app(
            self.tmp_path, "web", public_host="web.test", extra={"scaling": _SCALING}
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack, edge=EdgeConfig(http=80, https=443, streams=())).render()
        listeners = (
            self.tmp_path / "generated/nginx/gate-http/listeners.conf"
        ).read_text(encoding="utf-8")
        assert "scaling:web" in listeners
        assert "holding.html" in listeners
        assert "/wake/web" in listeners
        assert "/activity/web" in listeners
        assert "server_name web.test" in listeners

    def test_tls_scaling_snippet(self) -> None:
        write_applied_app(
            self.tmp_path, "web", public_host="web.test", tls="origin",
            extra={"scaling": _SCALING},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        (self.tmp_path / "certs" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack, edge=EdgeConfig(http=80, https=443, streams=())).render()
        tls = (self.tmp_path / "generated/nginx/gate-tls/web.conf").read_text(
            encoding="utf-8"
        )
        assert "holding.html" in tls and "listen 443 ssl" in tls

    def test_contribute_http_skips(self) -> None:
        gate = ScalingGate()
        ports = (PortSpec(name="http", container_port=80, expose="http"),)
        spec = AppSpec(ports=ports, scaling=ScalingSpec(1, 1, 1))
        empty = App(name="x", public_host="", source="local", path="apps/x")
        assert gate.contribute_http(empty, spec, edge=EdgeConfig(http=80)).gate_http == []
        hosted = App(name="y", public_host="y.test", source="local", path="apps/y")
        assert gate.contribute_http(hosted, spec, edge=EdgeConfig(http=None)).gate_http == []

    def test_tls_scaling_requires_https(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            public_host="web.test",
            tls="origin",
            extra={"scaling": _SCALING},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        with pytest.raises(Exception, match="edge.https"):
            StackRenderer(
                stack, edge=EdgeConfig(http=80, https=None, streams=())
            ).render()
