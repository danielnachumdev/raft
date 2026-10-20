"""FastAPI handlers for ``GET /api/events`` (ops timeline, read-only)."""

from typing import Any, Dict, Optional

from raft.core.core.models.stack import Stack
from raft.core.observe.ops.events import OpsEventsService
from raft.core.observe.ops.events.service import DEFAULT_HOURS, DEFAULT_LIMIT


class ServeEventsApi:
    """Localhost JSON API over ``host/events/ops.jsonl``."""

    def __init__(
        self, stack: Stack, *, service: Optional[OpsEventsService] = None
    ) -> None:
        self.stack = stack
        self._service = service or OpsEventsService(stack.root)

    def register(self, app) -> None:
        app.get("/api/events")(self.api_list)

    def api_list(
        self,
        hours: int = DEFAULT_HOURS,
        service: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> Dict[str, Any]:
        """Recent ops events (newest first); filter by kind / service / hours."""
        return self._service.list_events(
            hours=hours, service=service, kind=kind, limit=limit
        )
