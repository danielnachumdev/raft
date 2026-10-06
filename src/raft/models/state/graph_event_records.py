"""Typed GraphEvent producers used by lifecycle code paths."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..app import GATE_COMPOSE_ID
from ..graph_event import GraphEvent
from .graph_event_kinds import (
    KIND_DEPLOYMENT,
    KIND_DOWN,
    KIND_GATE_RECREATE,
    KIND_SCALING,
    KIND_START,
    KIND_STOP,
    KIND_UP,
    KIND_UPDATE,
    SCALING_ACTION_IDLE_STOP,
    SCALING_ACTION_WAKE,
)


class GraphEventRecords:
    """Mixin: convenience ``record_*`` helpers that call ``append``."""

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
        """CLI self-update when the installed identity actually changed."""
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
