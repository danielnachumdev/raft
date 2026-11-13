"""ASGI middleware: coarse authN/admission safety net (authZ via Depends)."""

from pathlib import Path
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.rbac import RbacEnforcer
from raft.core.core.rbac.identity import NONE_BOOTSTRAP_SUBJECT


class DashboardRbacMiddleware:
    """Ensure ``request.state.rbac_subject`` for ``/api/*`` (permission via Depends)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        home: Path,
        config: DashboardConfig,
    ) -> None:
        self.app = app
        self._home = home
        self._cfg = config
        self._enforcer = RbacEnforcer(home)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive=receive)
        denied = self._check(request)
        if denied is not None:
            await denied(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _check(self, request: Request) -> Optional[ASGIApp]:
        path = request.url.path
        if not path.startswith("/api/"):
            return None
        if path.startswith("/api/dashboard/"):
            return None
        if path == "/api/github/callback":
            return None
        subject = getattr(request.state, "rbac_subject", None)
        if not subject:
            if self._cfg.auth.mode == "none":
                request.state.rbac_subject = NONE_BOOTSTRAP_SUBJECT
                return None
            return self._json(401, "authentication required")
        if not self._enforcer.admitted(subject):
            return self._json(403, "subject not admitted")
        return None

    @staticmethod
    def _json(status: int, detail: str) -> ASGIApp:
        async def _send(scope: Scope, receive: Receive, send: Send) -> None:
            response: Response = JSONResponse({"detail": detail}, status_code=status)
            await response(scope, receive, send)

        return _send
