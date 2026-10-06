"""Integration: fixture app.yaml → apply/render → compose + nginx artifacts."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.config.settings_types import EdgeConfig
from tests.shared.artifacts import GeneratedArtifacts
from tests.shared.files import FileText
from tests.shared.raft_home import RaftHomeFixtures

pytestmark = pytest.mark.integration


class TestRenderHttpOnly:
    def test_int_http_only(self, isolated_raft_env: Path) -> None:
        gen = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env, RaftHomeFixtures.fixture_app_yamls("http_only")
            )
        )
        svc = gen.compose_apps()["services"]["http-only"]
        assert svc["image"] == "hashicorp/http-echo:1.0.0"
        assert 5678 in [int(x) for x in svc["expose"]]
        assert "ports" not in svc
        FileText.contains(gen.path("nginx", "router", "hosts.conf"), "http-only", "site.test")
        upstream = gen.path("nginx", "upstreams", "http-only-http.conf")
        assert upstream.is_file()
        FileText.contains(upstream, "server http-only:")
        FileText.contains(gen.path("compose.edge.yaml"), '"80:80"', '"443:443"')


class TestRenderHttpPlusStream:
    def test_int_http_plus_stream(self, isolated_raft_env: Path) -> None:
        gen = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env,
                RaftHomeFixtures.fixture_app_yamls("http_plus_stream"),
                edge=RaftHomeFixtures.edge_with_smtp_stream(),
            )
        )
        svc = gen.compose_apps()["services"]["http-plus-stream"]
        assert "ports" not in svc
        FileText.contains(gen.path("nginx", "gate-stream", "streams.conf"), "25")
        hosts = FileText.read(gen.path("nginx", "router", "hosts.conf"))
        assert "mail-ui.test" in hosts
        assert "smtp" not in hosts.lower() or "proxy_pass" in hosts


class TestRenderHostPublish:
    def test_int_host_publish(self, isolated_raft_env: Path) -> None:
        apps = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env, RaftHomeFixtures.fixture_app_yamls("host_publish")
            )
        ).compose_apps()
        svc = apps["services"]["host-publish"]
        ports = svc.get("ports") or []
        assert any("2525:25" in str(p) for p in ports)


class TestRenderExposeNoneVolume:
    def test_int_expose_none_volume(self, isolated_raft_env: Path) -> None:
        gen = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env,
                RaftHomeFixtures.fixture_app_yamls("expose_none_volume"),
            )
        )
        svc = gen.compose_apps()["services"]["demo-expose-none-vol"]
        assert svc["image"] == "redis:alpine"
        assert "ports" not in svc
        assert 6379 in [int(x) for x in svc["expose"]]
        assert svc["env_file"] == ["/tmp/raft-e2e-demo.env"]
        assert str(svc["environment"]["DEMO_FLAG"]) == "1"
        assert any("/tmp/raft-e2e-vol:/data" in str(v) for v in svc["volumes"])
        raw = gen.compose_apps_text()
        assert 'DEMO_FLAG: "1"' in raw or "DEMO_FLAG: '1'" in raw or "DEMO_FLAG: 1" in raw
        hosts = FileText.read(gen.path("nginx", "router", "hosts.conf"))
        assert "expose-none-vol" not in hosts
        FileText.contains(gen.path("compose.edge.yaml"), "raft-gate:")


class TestRenderMultiAppGroup:
    def test_int_multi_app_group(self, isolated_raft_env: Path) -> None:
        yamls = RaftHomeFixtures.fixture_app_yamls("multi_app_group")
        ordered = sorted(yamls, key=lambda p: 0 if "redis" in str(p) else 1)
        apps = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(isolated_raft_env, ordered)
        ).compose_apps()
        front = apps["services"]["demo-stack-front"]
        assert "demo-stack-redis" in front["depends_on"]
        assert front["depends_on"]["demo-stack-redis"]["condition"] == "service_started"
        router = apps["services"]["raft-router"]
        assert "demo-stack-front" in router["depends_on"]
        assert "demo-stack-redis" in router["depends_on"]


class TestRenderTlsOrigin:
    def test_int_tls_origin(self, isolated_raft_env: Path) -> None:
        gen = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env, RaftHomeFixtures.fixture_app_yamls("tls_origin")
            )
        )
        FileText.contains(
            gen.path("nginx", "gate-tls", "tls-origin.conf"),
            "listen 443 ssl",
            "certs/tls-origin/origin.pem",
        )


class TestRenderTlsAcme:
    def test_int_tls_acme_challenge_and_no_tls_without_pems(
        self, isolated_raft_env: Path
    ) -> None:
        gen = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env, RaftHomeFixtures.fixture_app_yamls("tls_acme")
            )
        )
        listeners = FileText.read(gen.path("nginx", "gate-http", "listeners.conf"))
        assert "acme_challenge.inc" in listeners or "proxy_router.inc" in listeners
        product = (
            isolated_raft_env / "nginx" / "gate" / "proxy_router.inc"
        ).read_text(encoding="utf-8")
        assert "acme_challenge.inc" in product
        assert product.index("acme_challenge.inc") < product.index("location /")
        assert list(gen.path("nginx", "gate-tls").glob("*.conf")) == []

    def test_int_tls_acme_with_pems(self, isolated_raft_env: Path) -> None:
        RaftHomeFixtures.prepare(isolated_raft_env)
        d = isolated_raft_env / "certs" / "tls-acme"
        d.mkdir(parents=True)
        (d / "acme.pem").write_text("pem\n", encoding="utf-8")
        (d / "acme.key").write_text("key\n", encoding="utf-8")
        gen = GeneratedArtifacts(
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env, RaftHomeFixtures.fixture_app_yamls("tls_acme")
            )
        )
        body = FileText.read(gen.path("nginx", "gate-tls", "tls-acme.conf"))
        assert "acme.pem" in body
        assert "origin.pem" not in body

    def test_int_tls_acme_requires_edge_http(self, isolated_raft_env: Path) -> None:
        with pytest.raises(Exception, match="edge.http"):
            RaftHomeFixtures.apply_and_render(
                isolated_raft_env,
                RaftHomeFixtures.fixture_app_yamls("tls_acme"),
                edge=EdgeConfig(http=None, https=443, streams=()),
            )


class TestRenderEdgeSettings:
    def test_int_edge_settings(self, isolated_raft_env: Path) -> None:
        edge = FileText.read(
            GeneratedArtifacts(
                RaftHomeFixtures.apply_and_render(
                    isolated_raft_env,
                    RaftHomeFixtures.fixture_app_yamls("http_only"),
                    edge=EdgeConfig(http=8080, https=8443, streams=()),
                )
            ).path("compose.edge.yaml")
        )
        assert '"8080:8080"' in edge
        assert '"8443:8443"' in edge
        assert '"80:80"' not in edge
