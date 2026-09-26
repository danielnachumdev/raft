"""StackRenderer coverage for App manifests."""

from __future__ import annotations

import pytest

from raft.config.settings_types import EdgeConfig, EdgeStream
from raft.models.stack import load_stack
from raft.services.render import StackRenderer

from ...base import write_applied_app
from .base import ManifestTestCase

MAIL_PORTS_EXTRA = {
    "ports": [
        {"name": "http", "containerPort": 80, "expose": "http"},
        {"name": "smtp", "containerPort": 25, "expose": "stream", "publicPort": 25},
        {"name": "submission", "containerPort": 587, "expose": "host", "publicPort": 587},
    ],
    "readiness": {"type": "tcp", "port": "smtp"},
}

REDIS_EXTRA = {
    "ports": [{"name": "redis", "containerPort": 6379, "expose": "none"}],
    "readiness": {"type": "tcp", "port": "redis"},
    "group": "demo",
    "envFile": "/home/raft/.raft/demo.env",
    "env": {"FOO": "bar"},
    "volumes": [{
        "hostPath": "/mnt/raft-data/demo/redis",
        "containerPath": "/data",
        "readOnly": False,
    }],
}

FRONT_EXTRA = {
    "ports": [{"name": "smtp", "containerPort": 25, "expose": "host", "publicPort": 25}],
    "readiness": {"type": "tcp", "port": "smtp"},
    "group": "demo",
    "dependsOn": ["stack-redis"],
    "envFile": "/home/raft/.raft/demo.env",
}


class TestStackRenderer(ManifestTestCase):
    def test_render_http_only_no_tls_snippets(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="off")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        StackRenderer(load_stack(self.tmp_path)).render()
        apps_yaml = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "wget" in apps_yaml and 'expose:\n      - "80"' in apps_yaml
        edge_yaml = (self.tmp_path / "generated" / "compose.edge.yaml").read_text(encoding="utf-8")
        assert '"80:80"' in edge_yaml and '"443:443"' in edge_yaml
        hosts = (self.tmp_path / "generated" / "nginx" / "router" / "hosts.conf").read_text(
            encoding="utf-8"
        )
        assert "proxy_pass http://web_http" in hosts
        assert list((self.tmp_path / "generated" / "nginx" / "gate-tls").glob("*.conf")) == []
        assert (self.tmp_path / "generated" / "nginx" / "upstreams" / "web-http.conf").is_file()

    def test_render_tls_origin_writes_snippet(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        StackRenderer(load_stack(self.tmp_path)).render()
        tls = (self.tmp_path / "generated" / "nginx" / "gate-tls" / "web.conf").read_text(
            encoding="utf-8"
        )
        assert "listen 443 ssl" in tls and "certs/web/origin.pem" in tls

    def test_render_rejects_undeclared_stream_port(self) -> None:
        write_applied_app(
            self.tmp_path, "mail", public_host="mail.example.com",
            extra={
                "ports": [{"name": "smtp", "containerPort": 25, "expose": "stream", "publicPort": 25}],
                "readiness": {"type": "tcp", "port": "smtp"},
            },
        )
        (self.tmp_path / "apps" / "mail").mkdir(parents=True)
        with pytest.raises(RuntimeError, match="not declared in settings edge.streams"):
            StackRenderer(
                load_stack(self.tmp_path), edge=EdgeConfig(http=80, https=None, streams=())
            ).render()

    def test_render_stream_and_host(self) -> None:
        write_applied_app(
            self.tmp_path, "mail", public_host="mail.example.com", extra=MAIL_PORTS_EXTRA
        )
        (self.tmp_path / "apps" / "mail").mkdir(parents=True)
        edge = EdgeConfig(
            http=80, https=443, streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),)
        )
        StackRenderer(load_stack(self.tmp_path), edge=edge).render()
        self._assert_stream_host_artifacts()

    def _assert_stream_host_artifacts(self) -> None:
        apps = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert '"587:587"' in apps and "nc -z" in apps
        streams = (
            self.tmp_path / "generated" / "nginx" / "gate-stream" / "streams.conf"
        ).read_text(encoding="utf-8")
        assert "listen 25" in streams
        edge_yaml = (self.tmp_path / "generated" / "compose.edge.yaml").read_text(encoding="utf-8")
        assert '"25:25"' in edge_yaml

    def test_render_empty_apps(self) -> None:
        StackRenderer(load_stack(self.tmp_path)).render()
        text = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "services: {}" in text

    def test_validate_requires_build_context(self) -> None:
        write_applied_app(self.tmp_path, "web", build_context=None, extra={"build": {}})
        with pytest.raises(ValueError, match="context is required"):
            StackRenderer(load_stack(self.tmp_path)).render()

    def test_render_volumes_env_depends_on(self) -> None:
        self._seed_redis_and_front()
        StackRenderer(load_stack(self.tmp_path)).render()
        apps = (self.tmp_path / "generated" / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "env_file:" in apps and "/home/raft/.raft/demo.env" in apps
        assert "FOO: bar" in apps and "/mnt/raft-data/demo/redis:/data" in apps
        assert "demo-stack-redis:" in apps and "condition: service_started" in apps
        assert '"25:25"' in apps

    def _seed_redis_and_front(self) -> None:
        write_applied_app(
            self.tmp_path, "stack-redis", source="docker", image="redis",
            public_host="", build_context=None, extra=REDIS_EXTRA,
        )
        write_applied_app(
            self.tmp_path, "stack-front", source="docker", image="ghcr.io/example/nginx",
            public_host="", build_context=None, extra=FRONT_EXTRA,
        )
