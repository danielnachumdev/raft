"""Password login / auth-status routes for the dashboard."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from raft.core.core.config.paths import PackageRootFinder
from raft.core.core.db.dashboard_sessions import COOKIE_NAME, DashboardSessionStore
from raft.core.core.rbac import RbacEnforcer

from .cookies import DashboardSessionCookies
from .password_session import PasswordSessionAuth


class DashboardLoginRoutes:
    """Register ``/login`` + ``/api/dashboard/login|auth`` password endpoints."""

    def __init__(
        self,
        passwords: PasswordSessionAuth,
        store: DashboardSessionStore,
        *,
        home: Path,
    ) -> None:
        self._passwords = passwords
        self._store = store
        self._enforcer = RbacEnforcer(home)

    def register(self, app: FastAPI) -> None:
        @app.get("/login")
        def login_page() -> FileResponse:
            return self._login_html()

        @app.get("/api/dashboard/auth", response_model=None)
        def auth_status(request: Request) -> JSONResponse:
            return self._auth_status(request)

        @app.post("/api/dashboard/login")
        async def login(request: Request):
            return await self._login(request)

    def _auth_status(self, request: Request) -> JSONResponse:
        cookie = request.cookies.get(COOKIE_NAME)
        subject = self._store.subject_for(cookie)
        ok = subject is not None
        body = {
            "authenticated": ok,
            "mode": "password",
            "username": subject,
        }
        return JSONResponse(body, status_code=200 if ok else 401)

    async def _login(self, request: Request) -> JSONResponse:
        payload = await request.json()
        password = str((payload or {}).get("password") or "")
        username = str((payload or {}).get("username") or "admin")
        subject = self._passwords.verify(password, username=username)
        if subject is None:
            return JSONResponse({"detail": "invalid credentials"}, status_code=401)
        if not self._enforcer.admitted(subject):
            return JSONResponse(
                {"detail": "subject not admitted"},
                status_code=403,
            )
        minted = self._store.create(subject, auth_mode="password")
        response = JSONResponse({"ok": True, "username": subject})
        DashboardSessionCookies.attach(request, response, minted)
        return response

    @staticmethod
    def _login_html() -> FileResponse:
        path = PackageRootFinder().find() / "dashboard" / "login.html"
        return FileResponse(path, media_type="text/html; charset=utf-8")
