"""ASGI middleware: password session or external identity header."""

from typing import Optional, Set

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from raft.core.core.config.settings.dashboard_config import DashboardConfig

from .password_session import PasswordSessionAuth

_PUBLIC_PATHS = frozenset(
    {
        "/api/dashboard/login",
        "/api/dashboard/logout",
        "/api/dashboard/auth",
    }
)
_MUTATIVE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class DashboardAuthMiddleware:
    """Enforce dashboard auth modes from settings."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        config: DashboardConfig,
        sessions: Optional[PasswordSessionAuth] = None,
        public_paths: Optional[Set[str]] = None,
    ) -> None:
        self.app = app
        self._cfg = config
        self._sessions = sessions
        self._public = public_paths or set(_PUBLIC_PATHS)

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
        mode = self._cfg.auth.mode
        if mode == "none":
            return None
        path = request.url.path
        if path in self._public or path.startswith("/assets/"):
            return None
        if mode == "external":
            return self._external(request)
        if mode == "password":
            return self._password(request)
        return None

    def _external(self, request: Request) -> Optional[ASGIApp]:
        header = self._cfg.auth.identity_header
        if request.headers.get(header):
            return None
        return self._json(401, f"missing identity header {header}")

    def _password(self, request: Request) -> Optional[ASGIApp]:
        if self._sessions is None:
            return self._json(401, "password auth not configured")
        cookie = request.cookies.get(self._sessions.cookie_name())
        if not self._sessions.session_ok(cookie):
            return self._json(401, "authentication required")
        if request.method in _MUTATIVE:
            csrf = request.headers.get("X-CSRF-Token")
            if not self._sessions.csrf_ok(cookie, csrf):
                return self._json(403, "CSRF token missing or invalid")
        return None

    @staticmethod
    def _json(status: int, detail: str) -> ASGIApp:
        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            response: Response = JSONResponse({"detail": detail}, status_code=status)
            await response(scope, receive, send)

        return _app
