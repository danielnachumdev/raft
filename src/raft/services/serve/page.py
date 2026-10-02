"""Serve SPA shell (static) and JSON status / metrics APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi.responses import FileResponse

from ...models import Stack
from ..ops.status import Status
from ..read import MetricsRead, StatusRead
from .paths import ServePaths

# GET /api/status — shared read contract (see raft.services.read).
# GET /api/metrics — historical series from resources.jsonl (poll + since).
# GET / — compiled React SPA from share/serve/spa (no second process).


class ServePage:
    """Localhost dashboard: static SPA + status/metrics JSON APIs."""

    def __init__(self, stack: Stack, status: Optional[Status] = None) -> None:
        self.stack = stack
        self._read = StatusRead(stack, status=status)
        self._metrics = MetricsRead(stack.root)

    def index(self) -> FileResponse:
        """Fast shell — packaged index.html; does not call Status.collect()."""
        return FileResponse(ServePaths.spa_index(), media_type="text/html")

    def api_status(self) -> Dict[str, Any]:
        """Expensive snapshot for the SPA (and future consumers)."""
        return self._read.api_payload()

    def api_metrics(
        self,
        window: int = 3600,
        since: Optional[str] = None,
        services: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Historical CPU/memory series; ``since`` enables incremental polls."""
        return self._metrics.history(
            window_seconds=window,
            since=since,
            services=self._split_services(services),
        )

    @staticmethod
    def _split_services(raw: Optional[str]) -> Optional[List[str]]:
        if raw is None or not raw.strip():
            return None
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts or None
