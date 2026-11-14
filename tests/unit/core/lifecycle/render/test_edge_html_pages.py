"""Unit tests for app-owned edge HTML page install + Host aliases."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.ports import PortSpec
from raft.core.lifecycle.render.acl.http_gate_host import HttpGateHost
from raft.core.lifecycle.render.edge_html_pages import EdgeHtmlPages

from tests.unit.base import RaftTestCase, AppliedInventory

_EDGE = EdgeConfig(http=80, https=443, streams=())
_PORTS = (PortSpec(name="http", container_port=80, expose="http"),)
_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 60,
    "minUpSeconds": 30,
}


class TestEdgeHtmlPages(RaftTestCase):
    def test_install_and_alias_in_host_block(self) -> None:
        self._write_pages_app()
        gen = self.render_applied(edge=_EDGE)
        self._assert_installed(gen)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "acl-host:web" in conf
        self._assert_aliases(conf)

    def test_prunes_stale_when_override_removed(self) -> None:
        dest = self._render_with_unavailable()
        assert dest.is_file()
        AppliedInventory.write_applied_app(
            self.tmp_path, "web", public_host="web.test"
        )
        self.render_applied(edge=_EDGE)
        assert not dest.is_file()

    def test_installs_maintenance_override(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "web",
            public_host="web.test",
            extra={"maintenancePage": ".raft/maintenance.html"},
        )
        raft = self.tmp_path / "services" / "web" / "checkout" / ".raft"
        raft.mkdir(parents=True, exist_ok=True)
        (raft / "maintenance.html").write_text("<html>m</html>", encoding="utf-8")
        gen = self.render_applied(edge=_EDGE)
        dest = gen / "nginx/gate-http/maintenance/web.html"
        assert dest.is_file() and "m" in dest.read_text(encoding="utf-8")
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert EdgeHtmlPages.maintenance_alias("web") in conf
        assert "acl-host:web" in conf

    def test_missing_checkout_errors(self) -> None:
        app = App(
            name="web",
            public_host="web.test",
            source="local",
            path="services/web/checkout",
        )
        spec = AppSpec(ports=_PORTS, unavailable_page=".raft/unavailable.html")
        with pytest.raises(OperatorError, match="checkout missing"):
            EdgeHtmlPages().install(self.tmp_path, [app], {"web": spec})

    def test_missing_file_errors(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "web",
            public_host="web.test",
            extra={"unavailablePage": ".raft/unavailable.html"},
        )
        with pytest.raises(OperatorError, match="unavailablePage"):
            self.render_applied(edge=_EDGE)

    def test_scaling_host_aliases_unavailable_override(self) -> None:
        self._write_pages_app(extra_scaling=_SCALING)
        gen = self.render_applied(edge=_EDGE)
        conf = (gen / "nginx/gate-http/listeners.conf").read_text(encoding="utf-8")
        assert "scaling:web" in conf
        self._assert_aliases(conf)

    def test_http_gate_host_skips_without_http_edge(self) -> None:
        app = self._sample_app()
        host = HttpGateHost()
        pages = AppSpec(ports=_PORTS, unavailable_page=".raft/u.html")
        empty = host.contribute(app, pages, edge=EdgeConfig(http=None), acl_include="")
        assert empty.gate_http == []
        with_acl = host.contribute(app, pages, edge=_EDGE, acl_include="include x;\n")
        assert with_acl.gate_http
        self._assert_host_skips(host, app)

    def test_symlink_escape_errors(self) -> None:
        app_root = self.tmp_path / "services" / "web" / "checkout"
        app_root.mkdir(parents=True, exist_ok=True)
        outside = self.tmp_path / "outside.html"
        outside.write_text("<html>nope</html>", encoding="utf-8")
        (app_root / "page.html").symlink_to(outside)
        app = self._sample_app()
        spec = AppSpec(ports=_PORTS, forbidden_page="page.html")
        with pytest.raises(OperatorError, match="escapes"):
            EdgeHtmlPages().install(self.tmp_path, [app], {"web": spec})

    def _assert_host_skips(self, host: HttpGateHost, app: App) -> None:
        plain = AppSpec(ports=_PORTS)
        # Plain Host HTTP always gets a server (redeploy → maintenance.html).
        assert host.contribute(app, plain, edge=_EDGE, acl_include="").gate_http
        assert "/_raft_edge_down" in host.contribute(
            app, plain, edge=_EDGE, acl_include=""
        ).gate_http[0]
        stream = AppSpec(
            ports=(PortSpec(name="smtp", container_port=25, expose="stream"),),
            unavailable_page=".raft/u.html",
        )
        assert host.contribute(app, stream, edge=_EDGE, acl_include="").gate_http == []

    def _write_pages_app(self, *, extra_scaling: dict | None = None) -> None:
        extra: dict = {
            "unavailablePage": ".raft/unavailable.html",
            "forbiddenPage": ".raft/forbidden.html",
        }
        if extra_scaling is not None:
            extra["scaling"] = extra_scaling
        AppliedInventory.write_applied_app(
            self.tmp_path, "web", public_host="web.test", extra=extra
        )
        raft = self.tmp_path / "services" / "web" / "checkout" / ".raft"
        raft.mkdir(parents=True, exist_ok=True)
        (raft / "unavailable.html").write_text("<html>u</html>", encoding="utf-8")
        (raft / "forbidden.html").write_text("<html>f</html>", encoding="utf-8")

    def _assert_installed(self, gen: Path) -> None:
        unavail = gen / "nginx/gate-http/unavailable/web.html"
        forbid = gen / "nginx/gate-http/forbidden/web.html"
        assert unavail.is_file() and "u" in unavail.read_text(encoding="utf-8")
        assert forbid.is_file() and "f" in forbid.read_text(encoding="utf-8")

    @staticmethod
    def _assert_aliases(conf: str) -> None:
        assert EdgeHtmlPages.unavailable_alias("web") in conf
        assert EdgeHtmlPages.forbidden_alias("web") in conf
        assert "error_page 502 503 504 =503 /_raft_edge_down;" in conf
        assert "/maintenance.html" in conf
        assert "deploy/redeploying" in conf

    def _render_with_unavailable(self) -> Path:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "web",
            public_host="web.test",
            extra={"unavailablePage": ".raft/unavailable.html"},
        )
        page = (
            self.tmp_path
            / "services"
            / "web"
            / "checkout"
            / ".raft"
            / "unavailable.html"
        )
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("<html>demo-api</html>", encoding="utf-8")
        self.render_applied(edge=_EDGE)
        return self.tmp_path / "generated/nginx/gate-http/unavailable/web.html"

    @staticmethod
    def _sample_app() -> App:
        return App(
            name="web",
            public_host="web.test",
            source="local",
            path="services/web/checkout",
        )
