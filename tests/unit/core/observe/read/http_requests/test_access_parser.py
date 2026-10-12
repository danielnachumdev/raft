"""Unit tests for HttpAccessLineParser."""

from raft.core.observe.read.http_requests import HttpAccessLineParser


class TestHttpAccessLineParser:
    def test_enriched_line(self) -> None:
        line = (
            '0.012 200 demo-api.test 2026-10-13T01:00:00+00:00 GET /health '
            '192.0.2.10 "DemoAgent/1.0"'
        )
        row = HttpAccessLineParser().parse(line)
        assert row is not None
        assert row.enriched is True
        assert row.host == "demo-api.test"
        assert row.method == "GET"
        assert row.path == "/health"
        assert row.client_ip == "192.0.2.10"
        assert row.duration_ms == 12.0
        assert row.to_api_row()["user_agent"] == "DemoAgent/1.0"

    def test_legacy_line(self) -> None:
        row = HttpAccessLineParser().parse("0.01 404 demo-api.test")
        assert row is not None
        assert row.enriched is False
        assert row.status == 404
        assert row.method is None

    def test_rejects_junk(self) -> None:
        assert HttpAccessLineParser().parse("not-a-line") is None
        assert HttpAccessLineParser().parse("0.1 200 -") is None

    def test_clips_long_path_and_ua(self) -> None:
        path = "/" + ("a" * 300)
        ua = "U" * 200
        line = (
            f'0.01 200 demo-api.test 2026-10-13T01:00:00+00:00 GET {path} '
            f'192.0.2.10 "{ua}"'
        )
        row = HttpAccessLineParser(path_max=20, ua_max=10).parse(line)
        assert row is not None
        assert len(row.path or "") <= 20
        assert (row.path or "").endswith("…")
        assert len(row.user_agent or "") <= 10
