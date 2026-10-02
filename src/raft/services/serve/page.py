"""Serve shell (fast HTML) and JSON status API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...models import Stack
from ..ops.status import Status
from .view import ServeSnapshotView

# GET /api/status JSON (contract for later FE #35 / trends #9):
# {
#   "host": { ... HostStatus.to_dict() ... },
#   "control_plane": [
#     {"name", "role", "group", "status", "cpu", "memory", "uptime"}, ...
#   ],
#   "apps": [ same row shape as control_plane ],
# }
# Rows use display labels (gate/router; group prefix stripped) and human
# cpu/memory/uptime strings — same columns as the Jinja tables.


class ServePage:
    """Localhost dashboard: shell HTML without Status; data via /api/status."""

    def __init__(
        self,
        stack: Stack,
        templates: Jinja2Templates,
        status: Optional[Status] = None,
    ) -> None:
        self.stack = stack
        self.templates = templates
        self._status = status if status is not None else Status(stack)

    def index(self, request: Request) -> HTMLResponse:
        """Fast shell — layout + spinner; does not call Status.collect()."""
        return self.templates.TemplateResponse(request, "index.html", {})

    def api_status(self) -> Dict[str, Any]:
        """Expensive snapshot for the client (and future SPA)."""
        return ServeSnapshotView(self._status.collect()).to_payload()
