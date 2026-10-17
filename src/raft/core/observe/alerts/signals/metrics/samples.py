"""Per-tick memoized JSONL sample reads."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from raft.core.observe.read.metrics.jsonl import MetricsJsonlReader

from ..context import SignalContext


class MetricsSampleCache:
    """Read JSONL once per (file, max window) per tick via SignalContext.memo."""

    def samples(
        self,
        ctx: SignalContext,
        path: Path,
        *,
        window_seconds: int,
    ) -> List[Dict[str, Any]]:
        key = f"metrics:{path}:{window_seconds}"
        return ctx.memo(key, lambda: self._load(path, ctx.now, window_seconds))

    @staticmethod
    def _load(path: Path, now: datetime, window_seconds: int) -> List[Dict[str, Any]]:
        if not path.is_file():
            return []
        from_ts = now - timedelta(seconds=window_seconds)
        return list(MetricsJsonlReader(path).samples_in_window(from_ts=from_ts))
