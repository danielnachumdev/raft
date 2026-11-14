"""Absent upstream park must 502 immediately (not self-proxy the router listen)."""

from raft.core.platform.adapters.nginx import NginxUpstreamText


class TestNginxUpstreamTextAbsentPark:
    def test_absent_server_is_marked_down(self) -> None:
        # Bare 127.0.0.1:80 accepts into raft-router's own listen and loops;
        # ``down`` forces 502 so gate error_page can serve unavailable.html.
        line = NginxUpstreamText.server_directive(
            NginxUpstreamText.ABSENT_HOSTNAME, 80
        )
        assert line == "server 127.0.0.1:80 down;"

    def test_absent_block_includes_down(self) -> None:
        body = NginxUpstreamText.block("demo-api_http", "127.0.0.1", 80)
        assert "server 127.0.0.1:80 down;" in body
        assert "server 127.0.0.1:80;" not in body

    def test_live_server_is_not_down(self) -> None:
        line = NginxUpstreamText.server_directive("demo-api", 80)
        assert line == "server demo-api:80;"
        assert "down" not in NginxUpstreamText.block("demo-api_http", "demo-api", 80)
