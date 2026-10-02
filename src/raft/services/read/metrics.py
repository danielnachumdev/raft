"""Historical resource series from ``state/metrics/resources.jsonl``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME

from .metrics_jsonl import MetricsJsonlReader
from .metrics_series import MetricsSeriesBuilder

DEFAULT_WINDOW_SECONDS = 3600
DEFAULT_MAX_POINTS = 480
WINDOW_CHOICES = (900, 3600, 21600, 86400, 604800)


class MetricsRead:
    """Shared reader for serve trends API (and future CLI consumers)."""

    def __init__(
        self,
        home: Path,
        *,
        reader: Optional[MetricsJsonlReader] = None,
        builder: Optional[MetricsSeriesBuilder] = None,
    ) -> None:
        self.home = home
        self.path = home / METRICS_DIR / METRICS_FILENAME
        self._reader = reader or MetricsJsonlReader(self.path)
        self._builder = builder or MetricsSeriesBuilder()

    def history(
        self,
        *,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        since: Optional[str] = None,
        services: Optional[Sequence[str]] = None,
        max_points: int = DEFAULT_MAX_POINTS,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        wall = now or datetime.now(timezone.utc)
        window = self._clamp_window(window_seconds)
        from_ts = wall - timedelta(seconds=window)
        since_ts = MetricsJsonlReader.parse_ts(since) if since else None
        samples = self._reader.samples_in_window(from_ts=from_ts, since=since_ts)
        return self._build_payload(
            samples, from_ts=from_ts, to_ts=wall, window=window,
            services=services, max_points=max_points,
        )

    @staticmethod
    def _clamp_window(window_seconds: int) -> int:
        if window_seconds in WINDOW_CHOICES:
            return window_seconds
        if window_seconds < 1:
            return DEFAULT_WINDOW_SECONDS
        return min(max(window_seconds, 60), WINDOW_CHOICES[-1])

    def _build_payload(
        self,
        samples: List[Dict[str, Any]],
        *,
        from_ts: datetime,
        to_ts: datetime,
        window: int,
        services: Optional[Sequence[str]],
        max_points: int,
    ) -> Dict[str, Any]:
        wanted = set(services) if services else None
        series_map = self._builder.build(samples, wanted=wanted)
        return {
            "window_seconds": window,
            "from": from_ts.isoformat(),
            "to": to_ts.isoformat(),
            "cursor": samples[-1].get("ts") if samples else None,
            "available": self._builder.available(samples),
            "series": [
                self._builder.downsample(s, max_points=max_points)
                for s in series_map.values()
            ],
        }
