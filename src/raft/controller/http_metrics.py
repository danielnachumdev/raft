"""Batched HTTP request metrics under ``state/metrics/http.jsonl``."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from raft.config.settings_types import (
    DEFAULT_METRICS_BATCH_SIZE,
    DEFAULT_METRICS_FLUSH_SECONDS,
    DEFAULT_METRICS_INTERVAL_SECONDS,
    DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
    DEFAULT_METRICS_RETENTION_MAX_BYTES,
)

from .http_metrics_scrape import GateHttpScraper
from .metrics import METRICS_DIR
from .metrics_rotation import MetricsRotation

logger = logging.getLogger(__name__)

HTTP_METRICS_FILENAME = "http.jsonl"

CollectFn = Callable[[], Dict[str, Any]]
ClockFn = Callable[[], float]


class HttpMetricsRecorder:
    """Sample gate HTTP runtime; batch-append sibling JSONL (same retention)."""

    def __init__(
        self,
        home: Path,
        *,
        interval_seconds: float = DEFAULT_METRICS_INTERVAL_SECONDS,
        batch_size: int = DEFAULT_METRICS_BATCH_SIZE,
        flush_seconds: float = DEFAULT_METRICS_FLUSH_SECONDS,
        retention_max_age_days: int = DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS,
        retention_max_bytes: int = DEFAULT_METRICS_RETENTION_MAX_BYTES,
        collect_fn: Optional[CollectFn] = None,
        clock: ClockFn = time.monotonic,
        rotation: Optional[MetricsRotation] = None,
        scraper: Optional[GateHttpScraper] = None,
    ) -> None:
        self.home = home
        self.batch_size = batch_size
        self.flush_seconds = flush_seconds
        self._collect_fn = collect_fn
        self._scraper = scraper or GateHttpScraper(
            home, interval_seconds=interval_seconds
        )
        self._clock = clock
        self._buffer: List[Dict[str, Any]] = []
        self._last_flush_at = clock()
        self._rotation = rotation or MetricsRotation(
            max_age_days=retention_max_age_days,
            max_bytes=retention_max_bytes,
        )

    @property
    def path(self) -> Path:
        return self.home / METRICS_DIR / HTTP_METRICS_FILENAME

    def tick(self) -> None:
        self._buffer.append(self._sample())
        if self._should_flush():
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

    def _sample(self) -> Dict[str, Any]:
        payload = self._collect_fn() if self._collect_fn else self._scraper.sample()
        return self._with_timestamp(payload)

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
            logger.error("http metrics append denied path=%s", self.path)
            raise
        logger.debug("http metrics flushed count=%s path=%s", len(rows), self.path)

    @staticmethod
    def _line(row: Dict[str, Any]) -> str:
        return json.dumps(row, separators=(",", ":")) + "\n"
