"""Batched resource utilization recording under ``~/.raft/state/metrics/``."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from raft.models.stack import Stack
from raft.services.ops.status import Status

logger = logging.getLogger(__name__)

METRICS_DIR = Path("state") / "metrics"
METRICS_FILENAME = "resources.jsonl"
DEFAULT_BATCH_SIZE = 10
DEFAULT_FLUSH_SECONDS = 60.0

CollectFn = Callable[[], Dict[str, Any]]
ClockFn = Callable[[], float]


class MetricsRecorder:
    """Sample via ``Status.collect``; buffer and append JSONL in batches."""

    def __init__(
        self,
        home: Path,
        *,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_seconds: float = DEFAULT_FLUSH_SECONDS,
        collect_fn: Optional[CollectFn] = None,
        clock: ClockFn = time.monotonic,
    ) -> None:
        self.home = home
        self.batch_size = batch_size
        self.flush_seconds = flush_seconds
        self._collect_fn = collect_fn
        self._clock = clock
        self._buffer: List[Dict[str, Any]] = []
        self._last_flush_at = clock()

    @property
    def path(self) -> Path:
        return self.home / METRICS_DIR / METRICS_FILENAME

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
        self._write_batch(rows)

    def _should_flush(self) -> bool:
        if len(self._buffer) >= self.batch_size:
            return True
        return (self._clock() - self._last_flush_at) >= self.flush_seconds

    def _sample(self) -> Dict[str, Any]:
        payload = self._collect_fn() if self._collect_fn else self._collect_status()
        return self._with_timestamp(payload)

    def _collect_status(self) -> Dict[str, Any]:
        status = Status(Stack(root=self.home, apps=()))
        return status.collect(refresh_apps=True).to_dict()

    @staticmethod
    def _with_timestamp(payload: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(payload)
        out.setdefault("ts", datetime.now(timezone.utc).isoformat())
        return out

    def _write_batch(self, rows: List[Dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        chunk = "".join(self._line(row) for row in rows)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(chunk)
        logger.debug("metrics flushed count=%s path=%s", len(rows), self.path)

    @staticmethod
    def _line(row: Dict[str, Any]) -> str:
        return json.dumps(row, separators=(",", ":")) + "\n"
