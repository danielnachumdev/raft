"""Integration: fixture app.yaml → apply/render → compose + nginx artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.config.settings import EdgeConfig

from tests.integration.shared.artifacts import load_compose_apps, read_text
from tests.shared.raft_home import (
    apply_and_render,
    edge_with_smtp_stream,
    fixture_app_yamls,
)

pytestmark = pytest.mark.integration


class TestRenderHttpOnly:
    def test_int_http_only(self, isolated_raft_env: Path) -> None:
        generated = apply_and_render(
            isolated_raft_env, fixture_app_yamls("http_only")
        )
        apps = load_compose_apps(generated)
        svc = apps["services"]["raft-http-only"]
        assert svc["image"] == "hashicorp/http-echo:1.0.0"
        assert 5678 in [int(x) for x in svc["expose"]]
        assert "ports" not in svc
        hosts = read_text(generated / "nginx" / "router" / "hosts.conf")
        assert "http-only" in hosts
        assert "site.test" in hosts
        upstream = generated / "nginx" / "upstreams" / "http-only-http.conf"
        assert upstream.is_file()
        assert "server raft-http-only:" in read_text(upstream)
        edge_raw = (generated / "compose.edge.yaml").read_text(encoding="utf-8")
        assert '"80:80"' in edge_raw
        assert '"443:443"' in edge_raw


class TestRenderHttpPlusStream:
    def test_int_http_plus_stream(self, isolated_raft_env: Path) -> None:
        generated = apply_and_render(
            isolated_raft_env,
            fixture_app_yamls("http_plus_stream"),
            edge=edge_with_smtp_stream(),
        )
        apps = load_compose_apps(generated)
        svc = apps["services"]["raft-http-plus-stream"]
        assert "ports" not in svc
        stream = read_text(generated / "nginx" / "gate-stream" / "streams.conf")
        assert "25" in stream
        hosts = read_text(generated / "nginx" / "router" / "hosts.conf")
        assert "mail-ui.test" in hosts
        assert "smtp" not in hosts.lower() or "proxy_pass" in hosts


class TestRenderHostPublish:
    def test_int_host_publish(self, isolated_raft_env: Path) -> None:
        generated = apply_and_render(
            isolated_raft_env, fixture_app_yamls("host_publish")
        )
        apps = load_compose_apps(generated)
        svc = apps["services"]["raft-host-publish"]
        ports = svc.get("ports") or []
        assert any("2525:25" in str(p) for p in ports)


class TestRenderExposeNoneVolume:
    def test_int_expose_none_volume(self, isolated_raft_env: Path) -> None:
        generated = apply_and_render(
            isolated_raft_env, fixture_app_yamls("expose_none_volume")
        )
        apps = load_compose_apps(generated)
        svc = apps["services"]["raft-demo-expose-none-vol"]
        assert svc["image"] == "redis:alpine"
        assert "ports" not in svc
        assert 6379 in [int(x) for x in svc["expose"]]
        assert svc["env_file"] == ["/tmp/raft-e2e-demo.env"]
        assert str(svc["environment"]["DEMO_FLAG"]) == "1"
        assert any("/tmp/raft-e2e-vol:/data" in str(v) for v in svc["volumes"])
        # Raw compose keeps quoted env values.
        raw = (generated / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "DEMO_FLAG: \"1\"" in raw or "DEMO_FLAG: '1'" in raw or "DEMO_FLAG: 1" in raw
        hosts = read_text(generated / "nginx" / "router" / "hosts.conf")
        # No Host routing for expose:none-only apps
        assert "expose-none-vol" not in hosts
        edge_raw = (generated / "compose.edge.yaml").read_text(encoding="utf-8")
        assert "raft-raft-gate:" in edge_raw


class TestRenderMultiAppGroup:
    def test_int_multi_app_group(self, isolated_raft_env: Path) -> None:
        yamls = fixture_app_yamls("multi_app_group")
        # Apply redis before front (dependsOn).
        ordered = sorted(yamls, key=lambda p: 0 if "redis" in str(p) else 1)
        generated = apply_and_render(isolated_raft_env, ordered)
        apps = load_compose_apps(generated)
        front = apps["services"]["raft-demo-stack-front"]
        assert "raft-demo-stack-redis" in front["depends_on"]
        assert front["depends_on"]["raft-demo-stack-redis"]["condition"] == "service_started"
        router = apps["services"]["raft-raft-router"]
        assert "raft-demo-stack-front" in router["depends_on"]
        assert "raft-demo-stack-redis" in router["depends_on"]


class TestRenderTlsOrigin:
    def test_int_tls_origin(self, isolated_raft_env: Path) -> None:
        generated = apply_and_render(
            isolated_raft_env, fixture_app_yamls("tls_origin")
        )
        tls = read_text(generated / "nginx" / "gate-tls" / "tls-origin.conf")
        assert "listen 443 ssl" in tls
        assert "certs/tls-origin/origin.pem" in tls


class TestRenderEdgeSettings:
    def test_int_edge_settings(self, isolated_raft_env: Path) -> None:
        generated = apply_and_render(
            isolated_raft_env,
            fixture_app_yamls("http_only"),
            edge=EdgeConfig(http=8080, https=8443, streams=()),
        )
        edge_raw = (generated / "compose.edge.yaml").read_text(encoding="utf-8")
        assert '"8080:8080"' in edge_raw
        assert '"8443:8443"' in edge_raw
        assert '"80:80"' not in edge_raw
