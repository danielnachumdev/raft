"""StackRenderer coverage for App manifests."""

from __future__ import annotations

import pytest

from raft.config.settings_types import EdgeConfig, EdgeStream
from tests.shared.artifacts import GeneratedArtifacts
from tests.shared.files import FileText

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
    "volumes": [
        {
            "hostPath": "/mnt/raft-data/demo/redis",
            "containerPath": "/data",
            "readOnly": False,
        }
    ],
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
        gen = GeneratedArtifacts(self.render_applied())
        FileText.contains(gen.path("compose.apps.yaml"), "wget", 'expose:\n      - "80"')
        FileText.contains(gen.path("compose.edge.yaml"), '"80:80"', '"443:443"')
        FileText.contains(gen.path("nginx", "router", "hosts.conf"), "proxy_pass http://web_http")
        assert list(gen.path("nginx", "gate-tls").glob("*.conf")) == []
        assert gen.path("nginx", "upstreams", "web-http.conf").is_file()

    def test_render_tls_origin_writes_snippet(self) -> None:
        write_applied_app(self.tmp_path, "web", public_host="web.test", tls="origin")
        gen = GeneratedArtifacts(self.render_applied())
        FileText.contains(
            gen.path("nginx", "gate-tls", "web.conf"),
            "listen 443 ssl",
            "certs/web/origin.pem",
        )

    def test_render_rejects_undeclared_stream_port(self) -> None:
        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
            extra={
                "ports": [
                    {"name": "smtp", "containerPort": 25, "expose": "stream", "publicPort": 25}
                ],
                "readiness": {"type": "tcp", "port": "smtp"},
            },
        )
        with pytest.raises(RuntimeError, match="not declared in settings edge.streams"):
            self.render_applied(edge=EdgeConfig(http=80, https=None, streams=()))

    def test_render_stream_and_host(self) -> None:
        write_applied_app(
            self.tmp_path, "mail", public_host="mail.example.com", extra=MAIL_PORTS_EXTRA
        )
        edge = EdgeConfig(
            http=80, https=443, streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),)
        )
        self.render_applied(edge=edge)
        self._assert_stream_host_artifacts()

    def _assert_stream_host_artifacts(self) -> None:
        gen = GeneratedArtifacts.under(self.tmp_path)
        FileText.contains(gen.path("compose.apps.yaml"), '"587:587"', "nc -z")
        FileText.contains(gen.path("nginx", "gate-stream", "streams.conf"), "listen 25")
        FileText.contains(gen.path("compose.edge.yaml"), '"25:25"')

    def test_render_empty_apps(self) -> None:
        gen = GeneratedArtifacts(self.render_applied())
        FileText.contains(gen.path("compose.apps.yaml"), "services: {}")

    def test_validate_requires_build_context(self) -> None:
        write_applied_app(self.tmp_path, "web", build_context=None, extra={"build": {}})
        with pytest.raises(ValueError, match="context is required"):
            self.render_applied()

    def test_render_volumes_env_depends_on(self) -> None:
        self._seed_redis_and_front()
        gen = GeneratedArtifacts(self.render_applied())
        FileText.contains(
            gen.path("compose.apps.yaml"),
            "env_file:",
            "/home/raft/.raft/demo.env",
            "FOO: bar",
            "/mnt/raft-data/demo/redis:/data",
            "demo-stack-redis:",
            "condition: service_started",
            '"25:25"',
        )

    def _seed_redis_and_front(self) -> None:
        write_applied_app(
            self.tmp_path,
            "stack-redis",
            source="docker",
            image="redis",
            public_host="",
            build_context=None,
            extra=REDIS_EXTRA,
        )
        write_applied_app(
            self.tmp_path,
            "stack-front",
            source="docker",
            image="ghcr.io/example/nginx",
            public_host="",
            build_context=None,
            extra=FRONT_EXTRA,
        )
