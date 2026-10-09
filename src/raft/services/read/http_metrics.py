"""Historical HTTP request series from ``state/metrics/http.jsonl``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from raft.config.settings import SettingsLoader
from raft.config.settings_types import MetricsConfig
from raft.controller.http_metrics import HTTP_METRICS_FILENAME
from raft.controller.metrics import METRICS_DIR

from .http_metrics_series import HttpMetricsSeriesBuilder
from .metrics import DEFAULT_MAX_POINTS
from .metrics_jsonl import MetricsJsonlReader
from .metrics_window import (
    DEFAULT_WINDOW_SECONDS,
    MetricsRangeQuery,
    ResolvedMetricsRange,
)


class HttpMetricsRead:
    """Shared reader for serve HTTP Trends (sibling of ``MetricsRead``)."""

    def __init__(
        self,
        home: Path,
        *,
        reader: Optional[MetricsJsonlReader] = None,
        builder: Optional[HttpMetricsSeriesBuilder] = None,
        metrics_config: Optional[MetricsConfig] = None,
    ) -> None:
        self.home = home
        self.path = home / METRICS_DIR / HTTP_METRICS_FILENAME
        self._reader = reader or MetricsJsonlReader(self.path)
        self._builder = builder or HttpMetricsSeriesBuilder()
        self._metrics_cfg = metrics_config or SettingsLoader().load(home).metrics

    def history(
        self,
        *,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        since: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        services: Optional[Sequence[str]] = None,
        max_points: int = DEFAULT_MAX_POINTS,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        wall = now or datetime.now(timezone.utc)
        query = self._query(wall)
        resolved = query.resolve(
            window_seconds=window_seconds, start=start, end=end
        )
        since_ts = MetricsJsonlReader.parse_ts(since) if since else None
        samples = self._reader.samples_in_window(
            from_ts=resolved.from_ts, since=since_ts, to_ts=resolved.to_ts
        )
        return self._finish_payload(samples, resolved, query, services, max_points)

    def _query(self, wall: datetime) -> MetricsRangeQuery:
        cfg = self._metrics_cfg
        return MetricsRangeQuery(
            max_age_days=cfg.retention_max_age_days,
            retention_max_bytes=cfg.retention_max_bytes,
            earliest=self._reader.earliest_ts(),
            now=wall,
        )

    def _finish_payload(
        self,
        samples: List[Dict[str, Any]],
        resolved: ResolvedMetricsRange,
        query: MetricsRangeQuery,
        services: Optional[Sequence[str]],
        max_points: int,
    ) -> Dict[str, Any]:
        wanted = set(services) if services else None
        series_map = self._builder.build(samples, wanted=wanted)
        payload = self._base_payload(samples, resolved, series_map, max_points)
        payload["bounds"] = query.bounds().to_mapping()
        payload["clamped"] = resolved.clamped
        if resolved.clamp_message:
            payload["clamp_message"] = resolved.clamp_message
        return payload

    def _base_payload(
        self,
        samples: List[Dict[str, Any]],
        resolved: ResolvedMetricsRange,
        series_map: Dict[str, Dict[str, Any]],
        max_points: int,
    ) -> Dict[str, Any]:
        return {
            "kind": "http",
            "window_seconds": resolved.window_seconds,
            "from": resolved.from_ts.isoformat(),
            "to": resolved.to_ts.isoformat(),
            "cursor": samples[-1].get("ts") if samples else None,
            "available": self._builder.available(samples),
            "series": [
                self._builder.downsample(s, max_points=max_points)
                for s in series_map.values()
            ],
            "percentile_window": "metrics.intervalSeconds sample window at the gate",
            "in_flight_proxy": "nginx stub_status Writing (Active also recorded)",
        }
