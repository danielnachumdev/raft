"""Gate proxy location unavailable page status for CDN passthrough."""

from pathlib import Path

from raft.core.core.config.paths import PackageRootFinder
from raft.core.lifecycle.render.acl.proxy_location import AclProxyLocation
from raft.core.lifecycle.render.edge_html_pages import EdgeHtmlPages


class TestAclProxyLocationUnavailable:
    def test_error_page_forces_503_for_unavailable_html(self) -> None:
        text = AclProxyLocation.location_slash(acl_include="")
        assert "error_page 502 503 504 =503 /unavailable.html;" in text
        assert "proxy_intercept_errors on;" in text

    def test_host_error_page_uses_chooser(self) -> None:
        text = AclProxyLocation.location_slash(
            acl_include="", app_name="demo-api"
        )
        assert "error_page 502 503 504 =503 /_raft_edge_down;" in text

    def test_shared_proxy_router_inc_matches(self) -> None:
        path = (
            PackageRootFinder().find() / "nginx" / "gate" / "proxy_router.inc"
        )
        text = Path(path).read_text(encoding="utf-8")
        assert "error_page 502 503 504 =503 /unavailable.html;" in text
        assert "/unavailable.html" in text
        assert "offline.html" not in text
        assert "maintenance.html" not in text

    def test_override_aliases_use_generated_paths(self) -> None:
        text = AclProxyLocation.unavailable_and_forbidden(
            acl_include="        include /x.inc;\n",
            unavailable_alias=EdgeHtmlPages.unavailable_alias("demo-api"),
            forbidden_alias=EdgeHtmlPages.forbidden_alias("demo-api"),
            maintenance_alias=EdgeHtmlPages.maintenance_alias("demo-api"),
            app_name="demo-api",
        )
        assert EdgeHtmlPages.unavailable_alias("demo-api") in text
        assert EdgeHtmlPages.forbidden_alias("demo-api") in text
        assert EdgeHtmlPages.maintenance_alias("demo-api") in text
        assert "/_raft_edge_down" in text
        assert "deploy/redeploying" in text

    def test_stock_unavailable_uses_errors_root(self) -> None:
        text = AclProxyLocation.unavailable_and_forbidden(acl_include="")
        assert "root /usr/share/nginx/errors" in text
        assert "_raft_forbidden" not in text
        assert "/_raft_edge_down" not in text

    def test_host_stock_includes_maintenance_chooser(self) -> None:
        text = AclProxyLocation.unavailable_and_forbidden(
            acl_include="", app_name="demo-api"
        )
        assert "/_raft_edge_down" in text
        assert "alias /usr/share/nginx/errors/maintenance.html" in text

    def test_send_timeout_line(self) -> None:
        text = AclProxyLocation.location_slash(
            acl_include="", send_timeout="120s"
        )
        assert "proxy_send_timeout 120s;" in text
