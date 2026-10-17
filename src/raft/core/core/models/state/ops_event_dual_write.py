"""Dual-write GraphEvents into the ops journal so shared kinds stay aligned."""

import logging
from typing import Optional

from .graph_event import GraphEvent
from .ops_event import OpsEvent
from .ops_event_kinds import OpsKindFromGraph
from .ops_event_store import OpsEventStore

logger = logging.getLogger(__name__)


class OpsEventDualWrite:
    """Append a mapped OpsEvent for a GraphEvent (Trends markers stay on graph.jsonl)."""

    def __init__(self, store: OpsEventStore) -> None:
        self._store = store

    def from_graph(self, event: GraphEvent) -> Optional[OpsEvent]:
        kind = OpsKindFromGraph.map(event)
        if kind is None:
            return None
        try:
            return self._store.append(
                OpsEvent(
                    kind=kind,
                    ts=event.ts,
                    summary=event.label or kind,
                    service=event.service,
                    metadata=dict(event.metadata),
                    id=event.id,
                )
            )
        except OSError:
            logger.warning(
                "ops dual-write failed kind=%s id=%s", kind, event.id, exc_info=True
            )
            return None
