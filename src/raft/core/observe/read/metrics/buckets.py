"""Time buckets that keep one metrics sample per chart pixel column."""

from datetime import datetime
from typing import Set


class MetricsSampleBuckets:
    """Track which ``bucket_seconds``-wide slots past ``origin`` hold a sample.

    ``bucket_seconds <= 0`` disables bucketing (every sample is kept).
    """

    def __init__(self, origin: datetime, bucket_seconds: float) -> None:
        self._origin = origin
        self._width = float(bucket_seconds)
        self._taken: Set[int] = set()

    def is_taken(self, ts: datetime) -> bool:
        if self._width <= 0:
            return False
        return self._slot(ts) in self._taken

    def claim(self, ts: datetime) -> None:
        if self._width > 0:
            self._taken.add(self._slot(ts))

    def _slot(self, ts: datetime) -> int:
        return int((ts - self._origin).total_seconds() // self._width)
