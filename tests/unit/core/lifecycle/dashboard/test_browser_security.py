"""Browser security header SoT for dashboard SPA / static HTML."""

from raft.core.lifecycle.dashboard.browser_security import BrowserSecurityHeaders
from tests.unit.base import RaftTestCase


class TestBrowserSecurityHeaders(RaftTestCase):
    def test_as_dict_omits_hsts_on_http(self) -> None:
        headers = BrowserSecurityHeaders().as_dict(https=False)
        assert "Strict-Transport-Security" not in headers
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "unsafe-inline" not in headers["Content-Security-Policy"]

    def test_as_dict_includes_hsts_on_https(self) -> None:
        headers = BrowserSecurityHeaders().as_dict(https=True)
        assert headers["Strict-Transport-Security"] == "max-age=15552000"
        assert "includeSubDomains" not in headers["Strict-Transport-Security"]
        assert "preload" not in headers["Strict-Transport-Security"]

    def test_inline_html_csp_allows_unsafe_inline(self) -> None:
        headers = BrowserSecurityHeaders().as_dict(https=False, inline_html=True)
        csp = headers["Content-Security-Policy"]
        assert "script-src 'self' 'unsafe-inline'" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_nginx_hsts_map_empty_on_non_https(self) -> None:
        text = BrowserSecurityHeaders.nginx_hsts_map()
        assert "map $raft_fwd_proto $raft_hsts" in text
        assert 'default ""' in text
        assert 'https   "max-age=15552000"' in text

    def test_nginx_add_header_lines_inline(self) -> None:
        text = BrowserSecurityHeaders().nginx_add_header_lines(inline_html=True)
        assert "add_header Content-Security-Policy" in text
        assert "unsafe-inline" in text
        assert "add_header X-Frame-Options DENY always" in text
        assert "add_header Strict-Transport-Security $raft_hsts always" in text

    def test_nginx_add_header_lines_spa_csp(self) -> None:
        text = BrowserSecurityHeaders().nginx_add_header_lines(inline_html=False)
        assert "script-src 'self'" in text
        assert "unsafe-inline" not in text
        assert "frame-ancestors 'none'" in text
