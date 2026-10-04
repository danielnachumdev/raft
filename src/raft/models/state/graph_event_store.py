"""Append-only GraphEvent JSONL under ``~/.raft/state/events/``.

Lifecycle producers append here; ``MetricsRead`` filters by the metrics window
so Trends / Runtime charts can draw markers without inferring history from
current deploy pins (pins only hold the live ref).
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Set

from ..graph_event import GraphEvent
from .graph_event_kinds import is_raft_level as raft_level_event
from .graph_event_records import GraphEventRecords

EVENTS_STATE_DIR = Path("state") / "events"
EVENTS_FILENAME = "graph.jsonl"


class GraphEventStore(GraphEventRecords):
    """Durable chart-event log (JSONL, one object per line)."""

    def __init__(self, home: Path) -> None:
        self.home = home
        self.path = home / EVENTS_STATE_DIR / EVENTS_FILENAME
        self._lock = threading.Lock()

    def ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: GraphEvent) -> GraphEvent:
        """Append one event; assigns ``id`` when missing. Returns stored event."""
        stored = self._with_id(event)
        line = json.dumps(stored.to_mapping(), separators=(",", ":")) + "\n"
        with self._lock:
            self.ensure_dir()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        return stored

    def events_in_window(
        self,
        *,
        from_ts: datetime,
        to_ts: Optional[datetime] = None,
        services: Optional[Sequence[str]] = None,
    ) -> List[GraphEvent]:
        """Chronological events with ``from_ts <= ts <= to_ts`` (service filter)."""
        wanted = set(services) if services is not None else None
        out: List[GraphEvent] = []
        for event in self._iter_parsed():
            if not self._in_window(event, from_ts=from_ts, to_ts=to_ts):
                continue
            if not self._service_wanted(event, wanted):
                continue
            out.append(event)
        return out

    def _iter_parsed(self) -> Iterator[GraphEvent]:
        if not self.path.is_file():
            return
        with self.path.open(encoding="utf-8") as handle:
            for raw in handle:
                event = self._parse_line(raw)
                if event is not None:
                    yield event

    @staticmethod
    def _parse_line(raw: str) -> Optional[GraphEvent]:
        line = raw.strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return GraphEvent.from_mapping(payload)

    @staticmethod
    def _in_window(
        event: GraphEvent,
        *,
        from_ts: datetime,
        to_ts: Optional[datetime],
    ) -> bool:
        ts = GraphEventStore._parse_ts(event.ts)
        if ts is None:
            return False
        if ts < from_ts:
            return False
        if to_ts is not None and ts > to_ts:
            return False
        return True

    @staticmethod
    def _service_wanted(
        event: GraphEvent, wanted: Optional[Set[str]]
    ) -> bool:
        if wanted is None:
            return True
        if GraphEventStore.is_raft_level(event):
            return True
        return event.service in wanted

    @staticmethod
    def is_raft_level(event: GraphEvent) -> bool:
        """Stack-wide / edge events — always relevant on Trends (and Runtime)."""
        return raft_level_event(event)

    @staticmethod
    def _parse_ts(value: str) -> Optional[datetime]:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _with_id(event: GraphEvent) -> GraphEvent:
        if event.id:
            return event
        return GraphEvent(
            kind=event.kind,
            ts=event.ts,
            service=event.service,
            label=event.label,
            metadata=dict(event.metadata),
            id=str(uuid.uuid4()),
        )
