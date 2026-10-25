"""Batched resource utilization recording under ``~/.raft/host/metrics/``."""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from raft.core.core.config.paths.metrics_paths import (
    METRICS_DIR,
    METRICS_FILENAME,
)
from raft.core.core.config.settings.types import (
    DEFAULT_METRICS_BATCH_SIZE,
    DEFAULT_METRICS_FLUSH_SECONDS,
    DEFAULT_METRICS_PRESSURE_THRESHOLD,
    DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_METRICS_RETENTION_MAX_BYTES,
)
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.status import Status
from raft.core.platform.adapters.host import CgroupMemory, HostGateway

from .rotation import MetricsRotation

logger = logging.getLogger(__name__)

CollectFn = Callable[[], Dict[str, Any]]
ClockFn = Callable[[], float]


class MetricsRecorder:
    """Sample via ``Status.collect`` (same gatherer as CLI/serve); batch JSONL.

    Under cgroup memory pressure, records a host-only sample (no ``docker
    stats``) and flushes immediately so the controller does not hold full
    Status snapshots while near its memcg limit.
    """

    def __init__(
        self,
        home: Path,
        *,
        batch_size: int = DEFAULT_METRICS_BATCH_SIZE,
        flush_seconds: float = DEFAULT_METRICS_FLUSH_SECONDS,
        retention_max_age_days: int = DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
        retention_max_bytes: int = DEFAULT_METRICS_RETENTION_MAX_BYTES,
        pressure_threshold: float = DEFAULT_METRICS_PRESSURE_THRESHOLD,
        collect_fn: Optional[CollectFn] = None,
        clock: ClockFn = time.monotonic,
        rotation: Optional[MetricsRotation] = None,
        memory: Optional[CgroupMemory] = None,
        host: Optional[HostGateway] = None,
    ) -> None:
        self.home = home
        self.batch_size = batch_size
        self.flush_seconds = flush_seconds
        self._pressure_threshold = pressure_threshold
        self._collect_fn = collect_fn
        self._clock = clock
        self._memory = memory or CgroupMemory()
        self._host = host or HostGateway(disk_path=home)
        self._buffer: List[Dict[str, Any]] = []
        self._last_flush_at = clock()
        self._rotation = rotation or MetricsRotation(
            max_age_days=retention_max_age_days,
            max_bytes=retention_max_bytes,
        )

    @property
    def path(self) -> Path:
        return self.home / METRICS_DIR / METRICS_FILENAME

    def tick(self) -> None:
        pressure = self._memory.elevated(threshold=self._pressure_threshold)
        self._buffer.append(self._sample(pressure=pressure))
        if pressure or self._should_flush():
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        rows = self._buffer
        self._buffer = []
        self._last_flush_at = self._clock()
        self._rotation.maintain(self.path)
        self._write_batch(rows)

    def _should_flush(self) -> bool:
        if len(self._buffer) >= self.batch_size:
            return True
        return (self._clock() - self._last_flush_at) >= self.flush_seconds

    def _sample(self, *, pressure: bool) -> Dict[str, Any]:
        if self._collect_fn is not None:
            payload = self._collect_fn()
        elif pressure:
            payload = self._host_only_sample()
        else:
            payload = self._collect_status()
        return self._with_timestamp(payload)

    def _collect_status(self) -> Dict[str, Any]:
        # Stack.load_apps skips ensure_raft_home: data home is mounted :ro.
        return Status(Stack.load_apps(self.home)).collect().to_dict()

    def _host_only_sample(self) -> Dict[str, Any]:
        """Lean sample when near the controller memcg limit (no Engine stats)."""
        logger.info("metrics host-only sample (memory pressure)")
        return {
            "host": Status._host_status(self._host).to_dict(),
            "containers": [],
            "degraded": "memory_pressure",
        }

    @staticmethod
    def _with_timestamp(payload: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(payload)
        out.setdefault("ts", datetime.now(timezone.utc).isoformat())
        return out

    def _write_batch(self, rows: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        chunk = "".join(self._line(row) for row in rows)
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(chunk)
        except PermissionError:
            self._log_permission_denied()
            raise
        logger.debug("metrics flushed count=%s path=%s", len(rows), self.path)

    def _log_permission_denied(self) -> None:
        logger.error(
            "metrics append denied path=%s — Trends stays empty until fixed. "
            'Fix: sudo chown "$(whoami):$(whoami)" %s',
            self.path,
            self.path,
        )

    @staticmethod
    def _line(row: Dict[str, Any]) -> str:
        return json.dumps(row, separators=(",", ":")) + "\n"
