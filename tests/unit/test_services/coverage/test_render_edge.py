"""Render / edge-stream coverage edges."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.config.settings_types import EdgeConfig, EdgeStream
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.stack import load_stack
from raft.services.render.edge import StreamEdge
from raft.services.render import StackRenderer

from ...base import RaftTestCase, make_app, write_applied_app


class TestRenderEdgeCoverage(RaftTestCase):
    def test_stream_protocol_mismatch_and_empty_edge(self) -> None:
        app = make_app("mail", public_host="mail.example.com")
        port = PortSpec(
            name="smtp",
            container_port=25,
            expose="stream",
            public_port=25,
            protocol="udp",
        )
        spec = AppSpec(ports=(port,))
        edge = EdgeConfig(streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),))
        with pytest.raises(RuntimeError, match="does not match"):
            StreamEdge().contribute(app, spec, port, edge=edge)

        write_applied_app(self.tmp_path, "web")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack, edge=EdgeConfig(http=None, https=None, streams=())).render()
        edge_yaml = (self.tmp_path / "generated" / "compose.edge.yaml").read_text(encoding="utf-8")
        assert "ports:\n      []" in edge_yaml

    def test_render_dockerfile_and_stale_prune(self) -> None:
        write_applied_app(
            self.tmp_path, "web",
            extra={"build": {"context": ".", "dockerfile": "Dockerfile.web"}},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        self._seed_stale_nginx(stack)
        StackRenderer(stack).render()
        self._assert_stale_pruned(stack)

    def _seed_stale_nginx(self, stack) -> None:
        for rel in ("nginx/gate-tls/stale.conf", "nginx/gate-http/old.conf"):
            path = stack.generated_dir() / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")
        up = stack.upstreams_dir
        up.mkdir(parents=True, exist_ok=True)
        (up / "old.conf").write_text("x", encoding="utf-8")

    def _assert_stale_pruned(self, stack) -> None:
        gen = stack.generated_dir()
        assert not (gen / "nginx" / "gate-tls" / "stale.conf").exists()
        assert not (gen / "nginx" / "gate-http" / "old.conf").exists()
        assert not (stack.upstreams_dir / "old.conf").exists()
        apps = (gen / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "dockerfile: Dockerfile.web" in apps

    def test_render_aliases_and_errors(self) -> None:
        write_applied_app(self.tmp_path, "web")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        renderer = StackRenderer(stack)
        specs = renderer.load_all_contracts()
        assert "web" in specs
        with pytest.raises(RuntimeError, match="missing AppSpec"):
            renderer.render(specs={})
        write_applied_app(
            self.tmp_path,
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            build_context=None,
        )
        stack2 = load_stack(self.tmp_path)
        StackRenderer(stack2).render()
        text = (stack2.generated_dir() / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "image: ghcr.io/org/hub:main" in text

    def test_render_build_outside_home(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            path="apps/web",
            extra={"build": {"context": "/tmp/outside-raft-build"}},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        with pytest.raises(ValueError, match="outside raft data home"):
            StackRenderer(stack).render()

    def test_stream_dir_stale_prune(self) -> None:
        write_applied_app(self.tmp_path, "web")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        stream_dir = stack.generated_dir() / "nginx" / "gate-stream"
        stream_dir.mkdir(parents=True, exist_ok=True)
        (stream_dir / "stale.conf").write_text("x", encoding="utf-8")
        StackRenderer(stack).render()
        assert not (stream_dir / "stale.conf").exists()

    def test_server_names_blank_extra(self) -> None:
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            www=False,
            extra_hosts=("  ",),
        )
        assert spec.server_names("a.test") == ("a.test",)
        assert spec.http_ports()[0].name == "http"
        assert spec.stream_ports() == ()
        assert spec.host_ports() == ()

    def test_gate_listener_https_only(self) -> None:
        write_applied_app(self.tmp_path, "web", tls="origin")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(stack, edge=EdgeConfig(http=None, https=443, streams=())).render()
        listeners = (stack.generated_dir() / "nginx" / "gate-http" / "listeners.conf").read_text(
            encoding="utf-8"
        )
        assert "listen 443 ssl" in listeners
        assert "listen 80" not in listeners

