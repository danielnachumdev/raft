"""Status helper/pure-function coverage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raft.services.ops.status.formatters import StatusFormatters
from raft.services.ops.status.service import Status


class TestStatusHelpers:
    def test_parse_started_at(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(hours=2, minutes=5)
        secs = Status._parse_started_at(started.isoformat().replace("+00:00", "Z"))
        assert secs is not None
        assert 7400 <= secs <= 7600
        assert Status._parse_started_at("") is None
        assert Status._parse_started_at("0001-01-01T00:00:00Z") is None
        assert Status._parse_started_at("not-a-date") is None
        naive = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(tzinfo=None)
        assert Status._parse_started_at(naive.isoformat()) is not None

    def test_formatters(self) -> None:
        assert StatusFormatters.bytes(None) == "-"
        assert StatusFormatters.bytes(-1) == "-"
        assert StatusFormatters.bytes(512) == "512B"
        assert StatusFormatters.bytes(1536) == "1.5KiB"
        assert StatusFormatters.bytes(1024**4) == "1.0TiB"
        assert StatusFormatters.percent(None) == "-"
        assert StatusFormatters.percent(12.34) == "12.3%"
        assert StatusFormatters.uptime(None) == "-"
        assert StatusFormatters.uptime(45) == "45s"
        assert StatusFormatters.uptime(3661) == "1h 1m"
        assert StatusFormatters.uptime(90061) == "1d 1h 1m"
