"""Serve SPA shell (static) and JSON status / metrics / action APIs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from raft.errors.cta import OperatorError

from ...models.stack import Stack
from ..ops.logs import DEFAULT_LOG_TAIL, Logs
from ..ops.status import Status
from ..read import MetricsRead, StatusRead
from .actions import ServeActions
from .log_stream import LogSseStream
from .paths import ServePaths

# GET /api/status — shared read contract (see raft.services.read).
# GET /api/metrics — historical series + GraphEvents (poll + since).
# GET /api/service/{name} — one Compose service from the status snapshot.
# GET /api/service/{name}/logs — container stdout/stderr tail (Logs.snapshot).
# GET /api/service/{name}/logs/follow — SSE follow (Logs.follow; CLI ``-f``).
# POST /api/service/{name}/start|stop|redeploy — mutative lifecycle actions.
# GET /api/exports + */download — ServeDownloads (export registry).
# GET / and non-API paths — compiled React SPA (deep-link fallback).

_MAX_LOG_TAIL = 5000
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class ServePage:
    """Localhost dashboard: static SPA + status/metrics/action JSON APIs."""

    def __init__(
        self,
        stack: Stack,
        status: Optional[Status] = None,
        actions: Optional[ServeActions] = None,
        logs: Optional[Logs] = None,
    ) -> None:
        self.stack = stack
        self._read = StatusRead(stack, status=status)
        self._metrics = MetricsRead(stack.root)
        self._actions = actions or ServeActions(stack)
        self._logs = logs or Logs(stack)

    def index(self, full_path: str = "") -> FileResponse:
        """SPA shell for ``/`` and client routes (not ``/api/*``)."""
        if self._is_api_path(full_path):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(ServePaths.spa_index(), media_type="text/html")

    def api_status(self) -> Dict[str, Any]:
        """Expensive snapshot for the SPA (and future consumers)."""
        payload = self._read.api_payload(refresh_apps=True)
        self._adopt_stack(self._read.stack)
        return payload

    def api_service(self, name: str) -> Dict[str, Any]:
        """Full status for one Compose service id."""
        detail = self._read.service_detail(name, refresh_apps=True)
        self._adopt_stack(self._read.stack)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"service '{name}' not found")
        return detail

    def _adopt_stack(self, stack: Stack) -> None:
        """Keep page + mutative collaborators on the reloaded registry."""
        if stack is self.stack:
            return
        self.stack = stack
        self._actions.bind_stack(stack)
        self._logs.bind_stack(stack)

    def api_service_logs(self, name: str, tail: int = DEFAULT_LOG_TAIL) -> Dict[str, Any]:
        """Recent container logs for one service (CLI ``raft logs`` snapshot)."""
        lines = self._clamp_tail(tail)
        try:
            text = self._logs.snapshot(name, tail=lines)
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc
        return {"service": name, "tail": lines, "text": text}

    def api_service_logs_follow(
        self, name: str, tail: int = DEFAULT_LOG_TAIL
    ) -> StreamingResponse:
        """SSE stream of follow lines (same ``Logs.follow`` as CLI ``-f``)."""
        lines = self._clamp_tail(tail)
        try:
            stream = self._logs.follow(name, tail=lines)
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc
        return StreamingResponse(
            LogSseStream.events(stream),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )

    def api_service_start(self, name: str) -> Dict[str, Any]:
        return self._run_action(self._actions.start, name)

    def api_service_stop(self, name: str) -> Dict[str, Any]:
        return self._run_action(self._actions.stop, name)

    def api_service_redeploy(self, name: str) -> Dict[str, Any]:
        return self._run_action(self._actions.redeploy, name)

    def api_metrics(
        self,
        window: int = 3600,
        since: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        services: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Historical series; ``start``/``end`` pin a range, ``since`` polls."""
        try:
            return self._metrics.history(
                window_seconds=window,
                since=since,
                start=start,
                end=end,
                services=self._split_services(services),
            )
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc

    def _run_action(self, fn, name: str) -> Dict[str, Any]:
        try:
            return fn(name)
        except OperatorError as exc:
            raise self._http_for_operator(exc) from exc

    @staticmethod
    def _clamp_tail(tail: int) -> int:
        if tail < 1:
            return 1
        if tail > _MAX_LOG_TAIL:
            return _MAX_LOG_TAIL
        return tail

    @staticmethod
    def _http_for_operator(exc: OperatorError) -> HTTPException:
        text = str(exc)
        code = 404 if text.startswith("unknown") else 400
        return HTTPException(status_code=code, detail=text)

    @staticmethod
    def _is_api_path(full_path: str) -> bool:
        return full_path == "api" or full_path.startswith("api/")

    @staticmethod
    def _split_services(raw: Optional[str]) -> Optional[List[str]]:
        if raw is None or not raw.strip():
            return None
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts or None
