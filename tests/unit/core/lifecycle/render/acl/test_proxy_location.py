"""Gate proxy location offline page status for CDN passthrough."""

from pathlib import Path

from raft.core.core.config.paths import PackageRootFinder
from raft.core.lifecycle.render.acl.proxy_location import AclProxyLocation


class TestAclProxyLocationOffline:
    def test_error_page_forces_503_for_offline_html(self) -> None:
        text = AclProxyLocation.location_slash(acl_include="")
        assert "error_page 502 503 504 =503 /offline.html;" in text
        assert "proxy_intercept_errors on;" in text

    def test_shared_proxy_router_inc_matches(self) -> None:
        path = (
            PackageRootFinder().find() / "nginx" / "gate" / "proxy_router.inc"
        )
        text = Path(path).read_text(encoding="utf-8")
        assert "error_page 502 503 504 =503 /offline.html;" in text
