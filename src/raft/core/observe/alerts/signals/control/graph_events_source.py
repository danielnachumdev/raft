"""control.events EVENT source from GraphEventStore."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

from raft.core.core.models.state.graph_event_store import GraphEventStore

from ...model.issues import ValidationIssue
from ..catalog_entries import graph_events_catalog
from ..context import SignalContext
from ..series import SignalPoint, SubjectSeries, ValueType
from ..signal_source import SignalSource

_KINDS = (
    "deployment",
    "service_down",
    "service_up",
    "scaling",
    "up",
    "down",
    "update",
    "gate_redeploy",
)


class GraphEventsSource(SignalSource):
    """Graph lifecycle events as EVENT series."""

    @property
    def type_id(self) -> str:
        return "control.events"

    @property
    def value_type(self) -> ValueType:
        return ValueType.EVENT

    def catalog_entry(self) -> Dict[str, Any]:
        return graph_events_catalog(self.type_id)

    def validate_select(
        self, select: Mapping[str, Any], *, path: str
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        if not isinstance(select.get("target"), str) or not select.get("target"):
            issues.append(ValidationIssue(f"{path}.target", "target is required"))
        kind = select.get("eventKind")
        if kind not in _KINDS:
            issues.append(
                ValidationIssue(f"{path}.eventKind", f"unknown eventKind {kind!r}")
            )
        return issues

    def query(
        self,
        select: Mapping[str, Any],
        *,
        window_seconds: int,
        ctx: SignalContext,
    ) -> List[SubjectSeries]:
        events = self._load(ctx, window_seconds)
        kind = str(select.get("eventKind"))
        action = select.get("action")
        filtered = self._filter(events, kind, action)
        return self._by_target(filtered, str(select.get("target")), kind)

    def _load(self, ctx: SignalContext, window_seconds: int):
        store = GraphEventStore(ctx.home)
        from_ts = ctx.now - timedelta(seconds=window_seconds)
        return store.events_in_window(from_ts=from_ts, to_ts=ctx.now)

    @staticmethod
    def _filter(events, kind: str, action) -> list:
        return [
            e
            for e in events
            if e.kind == kind
            and (not action or (e.metadata or {}).get("action") == action)
        ]

    def _by_target(self, filtered, target: str, kind: str) -> List[SubjectSeries]:
        if target == "-":
            points = self._points([e for e in filtered if not e.service], kind)
            return [SubjectSeries("-", tuple(points), wildcard=False)]
        if target == "*":
            return self._wildcard(filtered, kind)
        points = self._points([e for e in filtered if e.service == target], kind)
        return [SubjectSeries(target, tuple(points), wildcard=False)]

    def _wildcard(self, filtered, kind: str) -> List[SubjectSeries]:
        by_svc: Dict[str, List[SignalPoint]] = {}
        for e in filtered:
            if not e.service:
                continue
            point = self._point(e, kind)
            if point is not None:
                by_svc.setdefault(e.service, []).append(point)
        return [
            SubjectSeries(svc, tuple(pts), wildcard=True)
            for svc, pts in sorted(by_svc.items())
        ]

    def _points(self, events, kind: str) -> List[SignalPoint]:
        out: List[SignalPoint] = []
        for event in events:
            point = self._point(event, kind)
            if point is not None:
                out.append(point)
        return out

    def _point(self, event, kind: str) -> Optional[SignalPoint]:
        ts = self._parse_ts(event.ts)
        if ts is None:
            return None
        return SignalPoint(ts, kind)

    @staticmethod
    def _parse_ts(raw: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def describe(self, select: Mapping[str, Any]) -> str:
        return f"{select.get('target')} {select.get('eventKind')}"
