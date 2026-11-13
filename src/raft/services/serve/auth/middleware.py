"""ASGI middleware: authN + admission; sets ``request.state.rbac_subject``."""

from pathlib import Path
from typing import Optional, Set

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.db.dashboard_sessions import COOKIE_NAME, DashboardSessionStore
from raft.core.core.rbac import RbacEnforcer, RbacIdentity
from raft.core.core.rbac.identity import NONE_BOOTSTRAP_SUBJECT

from .cookies import DashboardSessionCookies

_PUBLIC_PATHS = frozenset(
    {
        "/login",
        "/api/dashboard/login",
        "/api/dashboard/logout",
        "/api/dashboard/auth",
        "/api/dashboard/session",
        "/api/github/callback",
    }
)
_MUTATIVE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_STATE_MINT = "_raft_mint_session"


class DashboardAuthMiddleware:
    """Reconfirm login/session; reject unbound subjects when RBAC is present."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        config: DashboardConfig,
        home: Path,
        store: Optional[DashboardSessionStore] = None,
        public_paths: Optional[Set[str]] = None,
    ) -> None:
        self.app = app
        self._cfg = config
        self._home = home
        self._store = store or DashboardSessionStore(home)
        self._enforcer = RbacEnforcer(home)
        self._identity = RbacIdentity(config)
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
        await self._forward(scope, receive, send, request)

    async def _forward(
        self, scope: Scope, receive: Receive, send: Send, request: Request
    ) -> None:
        minted = getattr(request.state, _STATE_MINT, None)
        if minted is None:
            await self.app(scope, receive, send)
            return

        async def send_with_cookie(message: dict) -> None:
            if message["type"] == "http.response.start":
                jar = Response()
                DashboardSessionCookies.attach(request, jar, minted)
                headers = list(message.get("headers") or [])
                headers.extend(
                    (name, value)
                    for name, value in jar.raw_headers
                    if name.lower() == b"set-cookie"
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cookie)

    def _check(self, request: Request) -> Optional[ASGIApp]:
        mode = self._cfg.auth.mode
        if mode == "none":
            request.state.rbac_subject = NONE_BOOTSTRAP_SUBJECT
            return None
        if request.url.path in self._public:
            return None
        cookie = request.cookies.get(COOKIE_NAME)
        subject = self._store.subject_for(cookie)
        if subject:
            return self._authed(request, subject, cookie)
        if mode in {"oauth", "external"}:
            return self._bootstrap_identity(request)
        if mode == "password":
            return self._unauthenticated(request)
        return None

    def _authed(
        self, request: Request, subject: str, cookie: Optional[str]
    ) -> Optional[ASGIApp]:
        if not self._enforcer.admitted(subject):
            return self._json(403, "subject not admitted")
        if request.method in _MUTATIVE and self._cfg.auth.mode == "password":
            csrf = request.headers.get("X-CSRF-Token")
            if not self._store.csrf_ok(cookie, csrf):
                return self._json(403, "CSRF token missing or invalid")
        request.state.rbac_subject = subject
        return None

    def _bootstrap_identity(self, request: Request) -> Optional[ASGIApp]:
        subject = self._identity.from_headers(request.headers)
        if not subject:
            return self._json(401, f"missing identity header {self._cfg.auth.identity_header}")
        if not self._enforcer.admitted(subject):
            return self._json(403, "subject not admitted")
        minted = self._store.create(subject, auth_mode=self._cfg.auth.mode)
        setattr(request.state, _STATE_MINT, minted)
        request.state.rbac_subject = subject
        return None

    def _unauthenticated(self, request: Request) -> ASGIApp:
        path = request.url.path
        if request.method == "GET" and not path.startswith("/api/"):
            return self._redirect("/login")
        return self._json(401, "authentication required")

    @staticmethod
    def _redirect(location: str) -> ASGIApp:
        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            response: Response = RedirectResponse(location, status_code=302)
            await response(scope, receive, send)

        return _app

    @staticmethod
    def _json(status: int, detail: str) -> ASGIApp:
        async def _app(scope: Scope, receive: Receive, send: Send) -> None:
            response: Response = JSONResponse({"detail": detail}, status_code=status)
            await response(scope, receive, send)

        return _app
