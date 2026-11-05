"""ASGI middleware: enforce RBAC on ``/api/*`` after admission."""

from pathlib import Path
from typing import Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.rbac import RbacEnforcer, RbacIdentity
from raft.core.core.rbac.http_gate import RbacHttpGate


class DashboardRbacMiddleware:
    """Deny API calls when ``rbac.yaml`` is present and subject lacks permission."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        home: Path,
        config: DashboardConfig,
        username_from_cookie: Optional[
            Callable[[Optional[str]], Optional[str]]
        ] = None,
    ) -> None:
        self.app = app
        self._home = home
        self._cfg = config
        self._gate = RbacHttpGate()
        self._enforcer = RbacEnforcer(home)
        self._identity = RbacIdentity(config)
        self._username_from_cookie = username_from_cookie

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
        permission = self._gate.permission(request.method, request.url.path)
        if permission is None:
            return None
        if not self._enforcer.file_present():
            return None
        username = None
        if self._username_from_cookie is not None:
            cookie = request.cookies.get("raft_dash_session")
            username = self._username_from_cookie(cookie)
        subject = self._identity.from_headers(
            request.headers, password_username=username
        )
        if not subject and self._cfg.auth.mode in {"oauth", "external"}:
            return self._json(401, "missing identity for RBAC")
        decision = self._enforcer.check(subject, permission)
        if decision.allowed:
            return None
        return self._json(403, f"RBAC denied {permission}")

    @staticmethod
    def _json(status: int, detail: str) -> ASGIApp:
        async def _send(scope: Scope, receive: Receive, send: Send) -> None:
            response: Response = JSONResponse({"detail": detail}, status_code=status)
            await response(scope, receive, send)

        return _send
