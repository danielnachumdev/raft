"""SSR index page built from a Status snapshot."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ...models import Stack
from ..ops.status import Status
from .view import ServeSnapshotView


class ServePage:
    """Render the localhost dashboard (read-only POC)."""

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
        snapshot = self._status.collect()
        view = ServeSnapshotView(snapshot)
        context: dict[str, Any] = {
            "control_plane": view.control_plane(),
            "apps": view.apps(),
            "host": snapshot.host,
        }
        return self.templates.TemplateResponse(request, "index.html", context)
