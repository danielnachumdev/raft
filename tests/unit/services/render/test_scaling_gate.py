"""Render emits gate holding/wake snippets for ``spec.scaling`` apps."""

from __future__ import annotations

import pytest

from raft.config.paths import find_package_root
from raft.config.settings_types import EdgeConfig
from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.scaling_spec import ScalingSpec
from raft.services.render.scaling_gate import ScalingGate
from tests.shared.files import FileText

from ...base import RaftTestCase, write_applied_app

_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 120,
    "minUpSeconds": 30,
}
_EDGE = EdgeConfig(http=80, https=443, streams=())


class TestScalingRender(RaftTestCase):
    def test_gate_http_includes_holding_and_wake(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", extra={"scaling": _SCALING})
        gen = self.render_applied(edge=_EDGE)
        FileText.contains(
            gen / "nginx/gate-http/listeners.conf",
            "scaling:web",
            "holding.html",
            "/wake/web",
            "/activity/web",
            "server_name web.test",
            "holding-timeout.html",
        )
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert conf.index("web.zero") < conf.index("web.timeout")
        assert conf.count("/_raft_wake_web") >= 2

    def test_timeout_location_enables_ssi_and_diag_alias(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", extra={"scaling": _SCALING})
        gen = self.render_applied(edge=_EDGE)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        hold_loc = conf[
            conf.index("location = /_raft_hold_web") : conf.index(
                "location = /_raft_timeout_web"
            )
        ]
        timed_loc = conf[
            conf.index("location = /_raft_timeout_web") : conf.index(
                "location = /_raft_timeout_diag"
            )
        ]
        assert "ssi on;" not in hold_loc
        assert "ssi on;" in timed_loc
        assert "web.id" in conf

    def test_timeout_page_has_admin_cta_and_holding_does_not(self) -> None:
        errors = find_package_root() / "nginx" / "errors"
        timeout = (errors / "holding-timeout.html").read_text(encoding="utf-8")
        holding = (errors / "holding.html").read_text(encoding="utf-8")
        assert "contact the administrator" in timeout
        assert 'include virtual="/_raft_timeout_diag"' in timeout
        assert "contact the administrator" not in holding
        assert "_raft_timeout_diag" not in holding

    def test_tls_scaling_snippet(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            public_host="web.test",
            tls="origin",
            extra={"scaling": _SCALING},
        )
        (self.tmp_path / "certs" / "web").mkdir(parents=True)
        gen = self.render_applied(edge=_EDGE)
        FileText.contains(gen / "nginx/gate-tls/web.conf", "holding.html", "listen 443 ssl")

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
        with pytest.raises(Exception, match="edge.https"):
            self.render_applied(edge=EdgeConfig(http=80, https=None, streams=()))
