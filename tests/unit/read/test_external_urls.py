"""Unit tests for external URL derivation from App + edge config."""

from __future__ import annotations

from typing import Optional

from raft.config.settings_types import EdgeConfig
from raft.models.app import App
from raft.models.stack import Stack
from raft.read import ExternalUrlBuilder

from tests.unit.base import RaftTestCase, make_app, make_stack, write_applied_app


class TestExternalUrlBuilder(RaftTestCase):
    def _builder(
        self,
        stack: Stack,
        *,
        http: Optional[int] = 80,
        https: Optional[int] = 443,
    ) -> ExternalUrlBuilder:
        return ExternalUrlBuilder(stack, EdgeConfig(http=http, https=https))

    def test_control_plane_roles_get_no_urls(self) -> None:
        write_applied_app(self.tmp_path, "site")
        stack = make_stack(self.tmp_path, (make_app("site"),))
        builder = self._builder(stack)
        for role in ("gate", "router", "controller"):
            assert builder.urls_for(service="raft-gate", role=role) == ()

    def test_unknown_service_gets_no_urls(self) -> None:
        write_applied_app(self.tmp_path, "site")
        stack = make_stack(self.tmp_path, (make_app("site"),))
        assert self._builder(stack).urls_for(service="missing", role="app") == ()

    def test_http_tls_off_uses_http(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="off")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack).urls_for(service="site", role="app")
        assert urls == ("http://site.test/",)

    def test_origin_tls_prefers_https(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="origin")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack).urls_for(service="site", role="app")
        assert urls == ("https://site.test/",)

    def test_acme_tls_prefers_https(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="acme")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack).urls_for(service="site", role="app")
        assert urls == ("https://site.test/",)

    def test_acme_tls_without_https_falls_back_to_http(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="acme")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack, http=80, https=None).urls_for(
            service="site", role="app"
        )
        assert urls == ("http://site.test/",)

    def test_custom_https_port_is_included(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="origin")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack, http=8080, https=8443).urls_for(
            service="site", role="app"
        )
        assert urls == ("https://site.test:8443/",)

    def test_custom_http_port_is_included(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="off")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack, http=8080, https=None).urls_for(
            service="site", role="app"
        )
        assert urls == ("http://site.test:8080/",)

    def test_https_only_edge_falls_back_to_https(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test", tls="off")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack, http=None, https=443).urls_for(
            service="site", role="app"
        )
        assert urls == ("https://site.test/",)

    def test_no_edge_listeners_yields_empty(self) -> None:
        write_applied_app(self.tmp_path, "site", public_host="site.test")
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        assert self._builder(stack, http=None, https=None).urls_for(
            service="site", role="app"
        ) == ()

    def test_extra_hosts_are_listed(self) -> None:
        write_applied_app(
            self.tmp_path,
            "site",
            public_host="site.test",
            tls="origin",
            extra={"extraHosts": ["www.site.test", "alias.test", "other.test"]},
        )
        stack = make_stack(self.tmp_path, (make_app("site", public_host="site.test"),))
        urls = self._builder(stack).urls_for(service="site", role="app")
        assert urls == (
            "https://site.test/",
            "https://www.site.test/",
            "https://alias.test/",
            "https://other.test/",
        )

    def test_grouped_compose_id_resolves(self) -> None:
        write_applied_app(
            self.tmp_path,
            "web",
            public_host="web.test",
            tls="off",
            extra={"group": "demo"},
        )
        app = App(
            name="web",
            public_host="web.test",
            source="local",
            path="apps/web",
            group="demo",
        )
        stack = make_stack(self.tmp_path, (app,))
        urls = self._builder(stack).urls_for(service="demo-web", role="app")
        assert urls == ("http://web.test/",)

    def test_empty_public_host_yields_empty(self) -> None:
        write_applied_app(
            self.tmp_path,
            "db",
            public_host="",
            extra={
                "ports": [
                    {"name": "pg", "containerPort": 5432, "expose": "none"},
                ],
                "readiness": {"type": "none"},
            },
        )
        stack = make_stack(
            self.tmp_path,
            (make_app("db", public_host=""),),
        )
        assert self._builder(stack).urls_for(service="db", role="app") == ()

    def test_no_http_ports_yields_empty(self) -> None:
        write_applied_app(
            self.tmp_path,
            "mail",
            public_host="mail.test",
            extra=self._stream_only_extra(),
        )
        stack = make_stack(
            self.tmp_path,
            (make_app("mail", public_host="mail.test"),),
        )
        assert self._builder(stack).urls_for(service="mail", role="app") == ()

    @staticmethod
    def _stream_only_extra() -> dict:
        return {
            "ports": [
                {
                    "name": "smtp",
                    "containerPort": 25,
                    "expose": "stream",
                    "publicPort": 25,
                },
            ],
            "readiness": {"type": "tcp", "port": "smtp"},
        }
