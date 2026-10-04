"""Render parks HTTP upstreams on loopback when apps are scaled to zero."""

from __future__ import annotations

from raft.adapters.nginx import NginxUpstreamText
from raft.models.ports import PortSpec
from raft.models.state.scaling_store import ScalingStore
from raft.models.stack import load_stack
from raft.services.render import StackRenderer
from raft.services.render.edge.fragments import EdgeFragments
from tests.shared.files import FileText

from ...base import RaftTestCase, make_app, write_applied_app

_SCALING = {
    "scaling": {
        "idleSeconds": 10,
        "wakeTimeoutSeconds": 30,
        "minUpSeconds": 5,
    }
}


class TestScaledUpstreamRender(RaftTestCase):
    def test_render_parks_scaled_upstream_on_loopback(self) -> None:
        write_applied_app(self.tmp_path, "web", extra=_SCALING)
        self.ensure_checkouts("web")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("web")
        StackRenderer(load_stack(self.tmp_path)).render()
        path = self.tmp_path / "generated" / "nginx" / "upstreams" / "web-http.conf"
        FileText.contains(path, f"server {NginxUpstreamText.ABSENT_HOSTNAME}:80")
        assert "server web:80" not in path.read_text(encoding="utf-8")

    def test_render_keeps_compose_hostname_when_awake(self) -> None:
        write_applied_app(self.tmp_path, "web")
        self.ensure_checkouts("web")
        StackRenderer(load_stack(self.tmp_path)).render()
        path = self.tmp_path / "generated" / "nginx" / "upstreams" / "web-http.conf"
        FileText.contains(path, "server web:80")

    def test_park_skips_non_http_and_missing_filename(self) -> None:
        app = make_app("web")
        frag = EdgeFragments(upstreams={"other.conf": "x"})
        stream = PortSpec(name="smtp", container_port=25, expose="stream")
        http = PortSpec(name="http", container_port=80, expose="http")
        StackRenderer._park_http_upstreams(frag, app, stream)
        assert frag.upstreams == {"other.conf": "x"}
        StackRenderer._park_http_upstreams(frag, app, http)
        assert frag.upstreams == {"other.conf": "x"}
