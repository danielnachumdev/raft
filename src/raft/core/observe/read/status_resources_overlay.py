"""Overlay container CPU/mem from controller ``resources.jsonl`` onto a lite snapshot."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.core.config.settings.types import DEFAULT_METRICS_INTERVAL_SECONDS
from raft.core.observe.ops.status.models import (
    ContainerStatus,
    IoPair,
    MemoryUsage,
    StatusSnapshot,
)
from .metrics.jsonl import MetricsJsonlReader

# Drop samples older than two scrape intervals so serve never paints stale stats.
_DEFAULT_MAX_AGE_SECONDS = 2.0 * DEFAULT_METRICS_INTERVAL_SECONDS


class StatusResourcesOverlay:
    """Fill resource fields from the newest controller metrics sample."""

    def __init__(
        self,
        home: Path,
        *,
        max_age_seconds: float = _DEFAULT_MAX_AGE_SECONDS,
        now: Optional[datetime] = None,
    ) -> None:
        self._home = home
        self._max_age_seconds = max_age_seconds
        self._now = now
        self._last_sample_ts: Optional[str] = None

    @property
    def resources_as_of(self) -> Optional[str]:
        """ISO timestamp of the sample used by the last ``apply``, if any."""
        return self._last_sample_ts

    def apply(self, snapshot: StatusSnapshot) -> StatusSnapshot:
        self._last_sample_ts = None
        sample = self._fresh_sample()
        if sample is None:
            return snapshot
        by_service = self._index_containers(sample)
        if not by_service:
            return snapshot
        self._last_sample_ts = self._ts_label(sample)
        containers = tuple(
            self._merge(row, by_service.get(row.service)) for row in snapshot.containers
        )
        return StatusSnapshot(host=snapshot.host, containers=containers)

    @staticmethod
    def _ts_label(sample: Mapping[str, Any]) -> Optional[str]:
        raw = sample.get("ts")
        if isinstance(raw, str) and raw.strip():
            return raw
        return None

    def _fresh_sample(self) -> Optional[Dict[str, Any]]:
        sample = MetricsJsonlReader(MetricsPaths(self._home).resources()).latest_sample()
        if sample is None:
            return None
        ts = MetricsJsonlReader.parse_ts(sample.get("ts"))
        if ts is None or self._is_stale(ts):
            return None
        return sample

    def _is_stale(self, ts: datetime) -> bool:
        now = self._now or datetime.now(timezone.utc)
        age = (now - ts).total_seconds()
        return age < 0 or age > self._max_age_seconds

    @staticmethod
    def _index_containers(sample: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
        rows = sample.get("containers")
        if not isinstance(rows, list):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("service")
            if isinstance(name, str) and name:
                out[name] = row
        return out

    def _merge(
        self, live: ContainerStatus, scraped: Optional[Mapping[str, Any]]
    ) -> ContainerStatus:
        if scraped is None:
            return live
        return ContainerStatus(
            service=live.service,
            role=live.role,
            app=live.app,
            group=live.group,
            status=live.status,
            uptime_seconds=live.uptime_seconds,
            cpu_percent=self._float(scraped.get("cpu_percent"), live.cpu_percent),
            memory=self._memory(scraped.get("memory"), live.memory),
            allocated=live.allocated,
            network=self._network(scraped.get("network"), live.network),
            block_io=self._block_io(scraped.get("block_io"), live.block_io),
            pids=self._int(scraped.get("pids"), live.pids),
        )

    @staticmethod
    def _memory(raw: Any, fallback: MemoryUsage) -> MemoryUsage:
        if not isinstance(raw, Mapping):
            return fallback
        return MemoryUsage(
            used_bytes=StatusResourcesOverlay._int(raw.get("used_bytes"), fallback.used_bytes),
            limit_bytes=StatusResourcesOverlay._int(
                raw.get("limit_bytes"), fallback.limit_bytes
            ),
            used_percent=StatusResourcesOverlay._float(
                raw.get("used_percent"), fallback.used_percent
            ),
        )

    @staticmethod
    def _network(raw: Any, fallback: IoPair) -> IoPair:
        if not isinstance(raw, Mapping):
            return fallback
        return IoPair(
            StatusResourcesOverlay._int(raw.get("rx_bytes"), fallback.rx_or_read_bytes),
            StatusResourcesOverlay._int(raw.get("tx_bytes"), fallback.tx_or_write_bytes),
        )

    @staticmethod
    def _block_io(raw: Any, fallback: IoPair) -> IoPair:
        if not isinstance(raw, Mapping):
            return fallback
        return IoPair(
            StatusResourcesOverlay._int(raw.get("read_bytes"), fallback.rx_or_read_bytes),
            StatusResourcesOverlay._int(raw.get("write_bytes"), fallback.tx_or_write_bytes),
        )

    @staticmethod
    def _float(raw: Any, fallback: Optional[float]) -> Optional[float]:
        if raw is None:
            return fallback
        try:
            return float(raw)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _int(raw: Any, fallback: Optional[int]) -> Optional[int]:
        if raw is None:
            return fallback
        try:
            return int(raw)
        except (TypeError, ValueError):
            return fallback
