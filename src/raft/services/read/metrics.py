"""Historical resource series from ``state/metrics/resources.jsonl``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from raft.config.settings import SettingsLoader
from raft.config.settings_types import MetricsConfig
from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME
from raft.models.state.graph_event_store import GraphEventStore

from .metrics_jsonl import MetricsJsonlReader
from .metrics_series import MetricsSeriesBuilder
from .metrics_window import (
    DEFAULT_WINDOW_SECONDS,
    PRESET_WINDOW_SECONDS,
    MetricsRangeQuery,
    ResolvedMetricsRange,
)

DEFAULT_MAX_POINTS = 480
WINDOW_CHOICES = PRESET_WINDOW_SECONDS


class MetricsRead:
    """Shared reader for serve trends API (and future CLI consumers)."""

    def __init__(
        self,
        home: Path,
        *,
        reader: Optional[MetricsJsonlReader] = None,
        builder: Optional[MetricsSeriesBuilder] = None,
        events: Optional[GraphEventStore] = None,
        metrics_config: Optional[MetricsConfig] = None,
    ) -> None:
        self.home = home
        self.path = home / METRICS_DIR / METRICS_FILENAME
        self._reader = reader or MetricsJsonlReader(self.path)
        self._builder = builder or MetricsSeriesBuilder()
        self._events = events or GraphEventStore(home)
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
        payload = self._build_payload(
            samples,
            from_ts=resolved.from_ts,
            to_ts=resolved.to_ts,
            window=resolved.window_seconds,
            services=services,
            max_points=max_points,
        )
        payload["bounds"] = query.bounds().to_mapping()
        payload["clamped"] = resolved.clamped
        if resolved.clamp_message:
            payload["clamp_message"] = resolved.clamp_message
        return payload

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
            "events": self._events_payload(
                from_ts=from_ts, to_ts=to_ts, services=services
            ),
        }

    def _events_payload(
        self,
        *,
        from_ts: datetime,
        to_ts: datetime,
        services: Optional[Sequence[str]],
    ) -> List[Dict[str, Any]]:
        events = self._events.events_in_window(
            from_ts=from_ts, to_ts=to_ts, services=services
        )
        return [event.to_mapping() for event in events]
