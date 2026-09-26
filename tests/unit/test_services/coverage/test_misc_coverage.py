"""Leftover coverage bits split into focused cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.config.settings import load_config
from raft.config.settings_types import EdgeConfig, EdgeStream
from raft.models.app import App
from raft.models.app_document import AppDocument
from raft.models.app_spec_fields import AppSpecFields
from raft.models.registry import AppRegistry
from raft.models.stack import load_stack
from raft.services.render import StackRenderer

from ...base import RaftTestCase, write_applied_app


UNIQ_DOC = {
    "apiVersion": "raft/v1",
    "kind": "App",
    "metadata": {"name": "uniq"},
    "spec": {
        "publicHost": "shared.test",
        "source": "local",
        "path": "apps/uniq",
        "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
        "build": {"context": "."},
    },
}


class TestMiscCoverage(RaftTestCase):
    def test_null_streams_loads_empty(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge:\n  streams: null\n", encoding="utf-8"
        )
        assert load_config(self.tmp_path).edge.streams == ()

    def test_parse_expect_name_and_bad_source(self) -> None:
        path = Path("x.yaml")
        doc = {
            "apiVersion": "raft/v1",
            "kind": "App",
            "metadata": {"name": "a"},
            "spec": {
                "publicHost": "a.test",
                "source": "local",
                "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
            },
        }
        with pytest.raises(ValueError, match="does not match expected"):
            AppDocument.parse(doc, path=path, expect_name="other")
        bad = {**doc, "spec": {**doc["spec"], "source": "ftp"}}
        with pytest.raises(ValueError, match="spec.source must be"):
            AppDocument.parse(bad, path=path)

    def test_docker_source_keeps_repo(self) -> None:
        app, _ = AppDocument.parse(
            {
                "apiVersion": "raft/v1",
                "kind": "App",
                "metadata": {"name": "hub"},
                "spec": {
                    "publicHost": "hub.test",
                    "source": "docker",
                    "image": "ghcr.io/org/hub",
                    "repo": "git@github.com:org/hub.git",
                    "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                },
            },
            path=Path("x.yaml"),
        )
        assert app.repo == "git@github.com:org/hub.git"

    def test_render_logs_debug_for_docker_build_context(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            source="docker",
            image="ghcr.io/org/web",
            build_context=None,
            extra={"build": {"context": "."}},
        )
        (self.tmp_path / "apps" / "web").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        with patch("raft.services.render.logger") as log:
            StackRenderer(stack).render()
            assert log.debug.called

    def test_render_host_udp_and_none_readiness(self) -> None:
        self._test_render_host_udp_and_none_readiness_p1()
        self._test_render_host_udp_and_none_readiness_p2()

    def _test_render_host_udp_and_none_readiness_p1(self) -> None:
        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.example.com",
            extra={
                "ports": [
                    {"name": "http", "containerPort": 80, "expose": "http"},
                    {
                        "name": "sub",
                        "containerPort": 587,
                        "expose": "host",
                        "publicPort": 587,
                        "protocol": "udp",
                    },
                ],
                "readiness": {"type": "none"},
            },
        )

    def _test_render_host_udp_and_none_readiness_p2(self) -> None:
        (self.tmp_path / "apps" / "mail").mkdir(parents=True)
        stack = load_stack(self.tmp_path)
        StackRenderer(
            stack,
            edge=EdgeConfig(
                http=80,
                https=443,
                streams=(EdgeStream(name="dns", port=53, protocol="udp"),),
            ),
        ).render()
        apps = (stack.generated_dir() / "compose.apps.yaml").read_text(encoding="utf-8")
        assert "587:587/udp" in apps
        edge_yaml = (stack.generated_dir() / "compose.edge.yaml").read_text(
            encoding="utf-8"
        )
        assert "53:53/udp" in edge_yaml
        mail_block = apps.split("  mail:\n", 1)[1]
        assert "healthcheck:" not in mail_block.split("    restart:", 1)[0]

    def test_image_ref_digest_and_resource_parsers(self) -> None:
        app = App(
            name="hub",
            public_host="hub.test",
            source="docker",
            path="apps/hub",
            image="ghcr.io/org/hub",
            ref="main",
        )
        assert app.image_ref("sha256:abc") == "ghcr.io/org/hub@sha256:abc"
        assert AppSpecFields._parse_cpu(2.5, default="0.1") == "2.5"
        assert AppSpecFields._parse_cpu("0.75", default="0.1") == "0.75"
        assert AppSpecFields._parse_memory("10Mi", default="1M") == "10M"
        assert AppSpecFields._parse_memory("128M", default="1M") == "128M"

    def test_parse_null_spec_tls_and_empty_extra_hosts(self) -> None:
        self._test_parse_null_spec_tls_and_empty_extra_hosts_p1()
        self._test_parse_null_spec_tls_and_empty_extra_hosts_p2()
        self._test_parse_null_spec_tls_and_empty_extra_hosts_p3()

    def _test_parse_null_spec_tls_and_empty_extra_hosts_p1(self) -> None:
        with pytest.raises(ValueError, match="spec.ports is required"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "bare"},
                    "spec": None,
                },
                path=Path("bare.yaml"),
            )

    def _test_parse_null_spec_tls_and_empty_extra_hosts_p2(self) -> None:
        with pytest.raises(ValueError, match="spec.tls must be"):
            AppDocument.parse(
                {
                    "apiVersion": "raft/v1",
                    "kind": "App",
                    "metadata": {"name": "a"},
                    "spec": {
                        "publicHost": "a.test",
                        "source": "local",
                        "tls": "bogus",
                        "ports": [
                            {"name": "http", "containerPort": 80, "expose": "http"}
                        ],
                    },
                },
                path=Path("x.yaml"),
            )

    def _test_parse_null_spec_tls_and_empty_extra_hosts_p3(self) -> None:
        _app2, spec2 = AppDocument.parse(
            {
                "apiVersion": "raft/v1",
                "kind": "App",
                "metadata": {"name": "a"},
                "spec": {
                    "publicHost": "a.test",
                    "source": "local",
                    "extraHosts": "",
                    "ports": [{"name": "http", "containerPort": 80, "expose": "http"}],
                    "build": {"context": "."},
                },
            },
            path=Path("x.yaml"),
        )
        assert spec2.extra_hosts == ()

    def test_registry_host_uniqueness(self) -> None:
        doc = UNIQ_DOC
        AppRegistry(self.tmp_path).write(doc)
        with pytest.raises(ValueError, match="already used"):
            AppRegistry(self.tmp_path).write(
                {**doc, "metadata": {"name": "other"},
                 "spec": {**doc["spec"], "path": "apps/other"}}
            )
        self._write_clash_host()
        with pytest.raises(ValueError, match="publicHost values must be unique"):
            load_stack(self.tmp_path)

    def _write_clash_host(self) -> None:
        other = self.tmp_path / "state" / "apps" / "clash.yaml"
        other.write_text(
            "apiVersion: raft/v1\nkind: App\nmetadata:\n  name: clash\nspec:\n"
            "  publicHost: shared.test\n  source: local\n"
            "  ports:\n    - name: http\n      containerPort: 80\n"
            "      expose: http\n  build:\n    context: .\n",
            encoding="utf-8",
        )
