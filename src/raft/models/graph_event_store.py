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
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set

from .app import CONTROLLER_COMPOSE_ID, GATE_COMPOSE_ID, ROUTER_COMPOSE_ID
from .graph_event import GraphEvent

EVENTS_STATE_DIR = Path("state") / "events"
EVENTS_FILENAME = "graph.jsonl"
KIND_DEPLOYMENT = "deployment"
KIND_STOP = "stop"
KIND_START = "start"
KIND_SCALING = "scaling"
KIND_UP = "up"
KIND_DOWN = "down"
KIND_UPDATE = "update"
KIND_GATE_RECREATE = "gate_recreate"
SCALING_ACTION_IDLE_STOP = "idle_stop"
SCALING_ACTION_WAKE = "wake"
RAFT_LEVEL_SERVICES = frozenset(
    {GATE_COMPOSE_ID, ROUTER_COMPOSE_ID, CONTROLLER_COMPOSE_ID}
)
RAFT_LEVEL_KINDS = frozenset(
    {KIND_UP, KIND_DOWN, KIND_UPDATE, KIND_GATE_RECREATE}
)


class GraphEventStore:
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

    def record_deployment(
        self,
        *,
        service: str,
        app: str,
        ref: str,
        ts: Optional[datetime] = None,
        label: Optional[str] = None,
    ) -> GraphEvent:
        """Convenience producer for apply / redeploy / cutover success."""
        return self._record(
            KIND_DEPLOYMENT,
            service=service,
            label=label or f"Deploy {app}",
            metadata={"app": app, "ref": ref},
            ts=ts,
        )

    def record_stop(
        self,
        *,
        service: str,
        app: Optional[str] = None,
        ts: Optional[datetime] = None,
        label: Optional[str] = None,
    ) -> GraphEvent:
        """Operator stop (serve/CLI) — not transient docker blips or heal restarts."""
        return self._record_named(
            KIND_STOP, service=service, app=app, ts=ts, label=label, verb="Stop"
        )

    def record_start(
        self,
        *,
        service: str,
        app: Optional[str] = None,
        ts: Optional[datetime] = None,
        label: Optional[str] = None,
    ) -> GraphEvent:
        """Operator start (serve) after an intentional stop / wake-adjacent start."""
        return self._record_named(
            KIND_START, service=service, app=app, ts=ts, label=label, verb="Start"
        )

    def record_scaling(
        self,
        *,
        service: str,
        app: str,
        action: str,
        ts: Optional[datetime] = None,
        label: Optional[str] = None,
    ) -> GraphEvent:
        """Scale-to-zero lifecycle (idle-stop / wake) for Trends markers."""
        return self._record(
            KIND_SCALING,
            service=service,
            label=label or self._scaling_label(app, action),
            metadata={"app": app, "action": action},
            ts=ts,
        )

    def record_stack_up(self, *, ts: Optional[datetime] = None) -> GraphEvent:
        """Full stack bring-up (``raft up`` / cold start)."""
        return self._record(KIND_UP, label="Stack up", metadata={}, ts=ts)

    def record_stack_down(self, *, ts: Optional[datetime] = None) -> GraphEvent:
        """Full stack tear-down (``raft down``)."""
        return self._record(KIND_DOWN, label="Stack down", metadata={}, ts=ts)

    def record_update(self, *, ts: Optional[datetime] = None) -> GraphEvent:
        """CLI self-update (``raft update``) completed."""
        return self._record(KIND_UPDATE, label="Raft update", metadata={}, ts=ts)

    def record_gate_recreate(self, *, ts: Optional[datetime] = None) -> GraphEvent:
        """Published-edge recreate (``raft gate recreate``)."""
        return self._record(
            KIND_GATE_RECREATE,
            service=GATE_COMPOSE_ID,
            label="Gate recreate",
            metadata={},
            ts=ts,
        )

    def _record_named(
        self,
        kind: str,
        *,
        service: str,
        app: Optional[str],
        ts: Optional[datetime],
        label: Optional[str],
        verb: str,
    ) -> GraphEvent:
        name = app or service
        meta: Dict[str, Any] = {}
        if app is not None:
            meta["app"] = app
        return self._record(
            kind,
            service=service,
            label=label or f"{verb} {name}",
            metadata=meta,
            ts=ts,
        )

    def _record(
        self,
        kind: str,
        *,
        label: str,
        metadata: Dict[str, Any],
        ts: Optional[datetime],
        service: Optional[str] = None,
    ) -> GraphEvent:
        when = ts or datetime.now(timezone.utc)
        return self.append(
            GraphEvent(
                kind=kind,
                ts=when.isoformat(),
                service=service,
                label=label,
                metadata=metadata,
            )
        )

    @staticmethod
    def _scaling_label(app: str, action: str) -> str:
        if action == SCALING_ACTION_IDLE_STOP:
            return f"Idle stop {app}"
        if action == SCALING_ACTION_WAKE:
            return f"Wake {app}"
        return f"Scale {app}"

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
        if event.service is None:
            return True
        if event.kind in RAFT_LEVEL_KINDS:
            return True
        return event.service in RAFT_LEVEL_SERVICES

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
