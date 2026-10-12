"""Render parks HTTP upstreams on loopback when apps are scaled to zero."""

from __future__ import annotations

from raft.core.platform.adapters.nginx import NginxUpstreamText
from raft.core.core.models.ports import PortSpec
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.render import StackRenderer
from raft.core.lifecycle.render.edge.fragments import EdgeFragments
from raft.core.lifecycle.render.fragment_collector import FragmentCollector
from tests.shared.files import FileText

from tests.unit.base import RaftTestCase, AppMakers, AppliedInventory

_SCALING = {
    "scaling": {
        "idleSeconds": 10,
        "wakeTimeoutSeconds": 30,
        "minUpSeconds": 5,
    }
}


class TestScaledUpstreamRender(RaftTestCase):
    def test_render_parks_scaled_upstream_on_loopback(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web", extra=_SCALING)
        self.ensure_checkouts("web")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("web")
        StackRenderer(load_stack(self.tmp_path)).render()
        path = self.tmp_path / "generated" / "nginx" / "upstreams" / "web-http.conf"
        FileText.contains(path, f"server {NginxUpstreamText.ABSENT_HOSTNAME}:80")
        assert "server web:80" not in path.read_text(encoding="utf-8")

    def test_render_keeps_compose_hostname_when_awake(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "web")
        self.ensure_checkouts("web")
        StackRenderer(load_stack(self.tmp_path)).render()
        path = self.tmp_path / "generated" / "nginx" / "upstreams" / "web-http.conf"
        FileText.contains(path, "server web:80")

    def test_park_skips_non_http_and_missing_filename(self) -> None:
        app = AppMakers.make_app("web")
        frag = EdgeFragments(upstreams={"other.conf": "x"})
        stream = PortSpec(name="smtp", container_port=25, expose="stream")
        http = PortSpec(name="http", container_port=80, expose="http")
        FragmentCollector._park_http_upstreams(frag, app, stream)
        assert frag.upstreams == {"other.conf": "x"}
        FragmentCollector._park_http_upstreams(frag, app, http)
        assert frag.upstreams == {"other.conf": "x"}
        FragmentCollector._park_http_upstreams(EdgeFragments(), app, http)
