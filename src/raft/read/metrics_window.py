"""Resolve metrics lookback / absolute range against retention bounds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from raft.errors.cta import OperatorError

from .metrics_jsonl import MetricsJsonlReader

MIN_WINDOW_SECONDS = 60
DEFAULT_WINDOW_SECONDS = 3600
PRESET_WINDOW_SECONDS = (900, 3600, 21600, 86400, 604800)


@dataclass(frozen=True)
class MetricsHistoryBounds:
    retention_max_age_days: int
    retention_max_bytes: int
    available_from: datetime
    earliest_ts: Optional[datetime]
    max_window_seconds: int

    def to_mapping(self) -> dict:
        earliest = self.earliest_ts.isoformat() if self.earliest_ts else None
        return {
            "retention_max_age_days": self.retention_max_age_days,
            "retention_max_bytes": self.retention_max_bytes,
            "available_from": self.available_from.isoformat(),
            "earliest_ts": earliest,
            "max_window_seconds": self.max_window_seconds,
        }


@dataclass(frozen=True)
class ResolvedMetricsRange:
    from_ts: datetime
    to_ts: datetime
    window_seconds: int
    clamped: bool
    clamp_message: Optional[str]


class MetricsRangeQuery:
    """Clamp ``window`` / ``start`` / ``end`` to retained metrics history."""

    def __init__(
        self,
        *,
        max_age_days: int,
        retention_max_bytes: int,
        earliest: Optional[datetime],
        now: datetime,
    ) -> None:
        self.now = now
        self.max_age_days = max(1, int(max_age_days))
        self.retention_max_bytes = int(retention_max_bytes)
        self.earliest = earliest
        self.retention_from = now - timedelta(days=self.max_age_days)
        self.available_from = self._available_from()
        self.max_window_seconds = int((now - self.retention_from).total_seconds())

    def bounds(self) -> MetricsHistoryBounds:
        return MetricsHistoryBounds(
            retention_max_age_days=self.max_age_days,
            retention_max_bytes=self.retention_max_bytes,
            available_from=self.available_from,
            earliest_ts=self.earliest,
            max_window_seconds=self.max_window_seconds,
        )

    def resolve(
        self,
        *,
        window_seconds: int,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> ResolvedMetricsRange:
        if start or end:
            return self._resolve_absolute(start, end, window_seconds)
        return self._resolve_relative(window_seconds)

    def _available_from(self) -> datetime:
        if self.earliest is None:
            return self.retention_from
        return max(self.retention_from, self.earliest)

    def _resolve_relative(self, window_seconds: int) -> ResolvedMetricsRange:
        window, clamped, message = self._clamp_window_seconds(window_seconds)
        return ResolvedMetricsRange(
            from_ts=self.now - timedelta(seconds=window),
            to_ts=self.now,
            window_seconds=window,
            clamped=clamped,
            clamp_message=message,
        )

    def _resolve_absolute(
        self,
        start_raw: Optional[str],
        end_raw: Optional[str],
        window_seconds: int,
    ) -> ResolvedMetricsRange:
        end = self._parse_end(end_raw)
        start = self._parse_start(start_raw, end, window_seconds)
        return self._finalize_absolute(start, end)

    def _parse_end(self, raw: Optional[str]) -> datetime:
        if raw is None or not str(raw).strip():
            return self.now
        return self._require_ts(raw, "end")

    def _parse_start(
        self, raw: Optional[str], end: datetime, window_seconds: int
    ) -> datetime:
        if raw is not None and str(raw).strip():
            return self._require_ts(raw, "start")
        window, _, _ = self._clamp_window_seconds(
            window_seconds if window_seconds >= 1 else DEFAULT_WINDOW_SECONDS
        )
        return end - timedelta(seconds=window)

    def _finalize_absolute(
        self, start: datetime, end: datetime
    ) -> ResolvedMetricsRange:
        notes: List[str] = []
        span = max(int((end - start).total_seconds()), MIN_WINDOW_SECONDS)
        end, end_notes = self._clamp_end(end)
        start, start_notes = self._clamp_start(start)
        notes.extend(end_notes)
        notes.extend(start_notes)
        if start >= end:
            end = min(self.now, start + timedelta(seconds=span))
            notes.append("Range was adjusted to fit available metrics history.")
        window = max(int((end - start).total_seconds()), MIN_WINDOW_SECONDS)
        return ResolvedMetricsRange(
            from_ts=start,
            to_ts=end,
            window_seconds=window,
            clamped=bool(notes),
            clamp_message=" ".join(notes) if notes else None,
        )

    def _clamp_end(self, end: datetime) -> Tuple[datetime, List[str]]:
        if end > self.now:
            return self.now, ["End is in the future; using now."]
        if end < self.available_from:
            return self.available_from, [self._too_old_msg()]
        return end, []

    def _clamp_start(self, start: datetime) -> Tuple[datetime, List[str]]:
        if start < self.available_from:
            return self.available_from, [self._too_old_msg()]
        return start, []

    def _clamp_window_seconds(
        self, window_seconds: int
    ) -> Tuple[int, bool, Optional[str]]:
        if window_seconds < 1:
            return DEFAULT_WINDOW_SECONDS, False, None
        if window_seconds < MIN_WINDOW_SECONDS:
            return MIN_WINDOW_SECONDS, True, None
        if window_seconds > self.max_window_seconds:
            return self.max_window_seconds, True, self._too_old_msg()
        return window_seconds, False, None

    def _too_old_msg(self) -> str:
        when = self.available_from.strftime("%Y-%m-%d %H:%M UTC")
        return (
            f"That time is older than retained metrics "
            f"({self.max_age_days} days; available from {when})."
        )

    @staticmethod
    def _require_ts(raw: str, field: str) -> datetime:
        parsed = MetricsJsonlReader.parse_ts(raw)
        if parsed is None:
            raise OperatorError(
                f"metrics {field} is not a valid ISO timestamp: {raw!r}.\n"
                f"Fix: pass an ISO-8601 datetime (for example 2026-10-01T12:00:00Z)"
            )
        return parsed
