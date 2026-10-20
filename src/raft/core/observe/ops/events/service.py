"""Query the durable ops event journal for CLI and serve."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from raft.core.core.models.state.ops_event_store import OpsEventStore

DEFAULT_HOURS = 24
MAX_HOURS = 168
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000


class OpsEventsService:
    """Read window over ``~/.raft/host/events/ops.jsonl`` (+ sealed archives)."""

    def __init__(
        self, home: Path, *, store: Optional[OpsEventStore] = None
    ) -> None:
        self.home = home
        self._store = store or OpsEventStore(home)

    def list_events(
        self,
        *,
        hours: int = DEFAULT_HOURS,
        service: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> Dict[str, Any]:
        """Return newest-first public rows for the requested window."""
        hours = self._clamp_hours(hours)
        limit = self._clamp_limit(limit)
        to_ts = datetime.now(timezone.utc)
        from_ts = to_ts - timedelta(hours=hours)
        services = [service] if service else None
        kinds = [kind] if kind else None
        rows = self._store.events_in_window(
            from_ts=from_ts, to_ts=to_ts, services=services, kinds=kinds
        )
        rows.reverse()
        trimmed = rows[:limit]
        return {
            "from": from_ts.isoformat(),
            "to": to_ts.isoformat(),
            "hours": hours,
            "count": len(trimmed),
            "events": [e.to_public() for e in trimmed],
        }

    @staticmethod
    def _clamp_hours(hours: int) -> int:
        try:
            value = int(hours)
        except (TypeError, ValueError):
            return DEFAULT_HOURS
        if value < 1:
            return 1
        return min(value, MAX_HOURS)

    @staticmethod
    def _clamp_limit(limit: int) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            return DEFAULT_LIMIT
        if value < 1:
            return 1
        return min(value, MAX_LIMIT)
