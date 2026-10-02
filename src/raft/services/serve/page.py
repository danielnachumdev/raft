"""Serve shell (fast HTML) and JSON status API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...models import Stack
from ..ops.status import Status
from ..read import StatusRead

# GET /api/status — shared read contract (see raft.services.read):
# Canonical body matches ``raft status --json`` (host + containers), plus
# presentation lists control_plane / apps for the current Jinja tables.
# Prefer ``containers`` for SPA (#35) / trends (#9).


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
        self._read = StatusRead(stack, status=status)

    def index(self, request: Request) -> HTMLResponse:
        """Fast shell — layout + spinner; does not call Status.collect()."""
        return self.templates.TemplateResponse(request, "index.html", {})

    def api_status(self) -> Dict[str, Any]:
        """Expensive snapshot for the client (and future SPA)."""
        return self._read.api_payload()
