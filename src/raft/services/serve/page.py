"""Serve SPA shell (static) and JSON status API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi.responses import FileResponse

from ...models import Stack
from ..ops.status import Status
from ..read import StatusRead
from .paths import ServePaths

# GET /api/status — shared read contract (see raft.services.read).
# GET / — compiled React SPA from share/serve/spa (no second process).


class ServePage:
    """Localhost dashboard: static SPA + /api/status from StatusRead."""

    def __init__(self, stack: Stack, status: Optional[Status] = None) -> None:
        self.stack = stack
        self._read = StatusRead(stack, status=status)

    def index(self) -> FileResponse:
        """Fast shell — packaged index.html; does not call Status.collect()."""
        return FileResponse(ServePaths.spa_index(), media_type="text/html")

    def api_status(self) -> Dict[str, Any]:
        """Expensive snapshot for the SPA (and future consumers)."""
        return self._read.api_payload()
