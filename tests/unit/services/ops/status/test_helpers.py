"""Status helper/pure-function coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raft.services.ops.status.report import (
    _fmt_bytes,
    _fmt_percent,
    _fmt_uptime,
)
from raft.services.ops.status.service import _parse_started_at


class TestStatusHelpers:
    def test_parse_started_at(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(hours=2, minutes=5)
        secs = _parse_started_at(started.isoformat().replace("+00:00", "Z"))
        assert secs is not None
        assert 7400 <= secs <= 7600
        assert _parse_started_at("") is None
        assert _parse_started_at("0001-01-01T00:00:00Z") is None
        assert _parse_started_at("not-a-date") is None
        naive = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(tzinfo=None)
        assert _parse_started_at(naive.isoformat()) is not None

    def test_formatters(self) -> None:
        assert _fmt_bytes(None) == "-"
        assert _fmt_bytes(-1) == "-"
        assert _fmt_bytes(512) == "512B"
        assert _fmt_bytes(1536) == "1.5KiB"
        assert _fmt_bytes(1024**4) == "1.0TiB"
        assert _fmt_percent(None) == "-"
        assert _fmt_percent(12.34) == "12.3%"
        assert _fmt_uptime(None) == "-"
        assert _fmt_uptime(45) == "45s"
        assert _fmt_uptime(3661) == "1h 1m"
        assert _fmt_uptime(90061) == "1d 1h 1m"


