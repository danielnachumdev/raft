"""Password login / logout / auth-status routes for the dashboard."""

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from raft.core.core.config.paths import PackageRootFinder

from .password_session import PasswordSessionAuth


class DashboardLoginRoutes:
    """Register ``/login`` + ``/api/dashboard/*`` password endpoints."""

    def __init__(self, sessions: PasswordSessionAuth) -> None:
        self._sessions = sessions

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

        @app.post("/api/dashboard/logout")
        def logout() -> JSONResponse:
            return self._logout_response()

    def _auth_status(self, request: Request) -> JSONResponse:
        cookie = request.cookies.get(self._sessions.cookie_name())
        ok = self._sessions.session_ok(cookie)
        return JSONResponse(
            {"authenticated": ok, "mode": "password"},
            status_code=200 if ok else 401,
        )

    async def _login(self, request: Request) -> JSONResponse:
        payload = await request.json()
        password = str((payload or {}).get("password") or "")
        tokens = self._sessions.login(password)
        if tokens is None:
            return JSONResponse({"detail": "invalid password"}, status_code=401)
        session, csrf = tokens
        response = JSONResponse({"ok": True})
        self._set_cookies(request, response, session, csrf)
        return response

    def _logout_response(self) -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(self._sessions.cookie_name())
        response.delete_cookie(self._sessions.csrf_cookie_name())
        return response

    def _set_cookies(
        self, request: Request, response: JSONResponse, session: str, csrf: str
    ) -> None:
        secure = self._secure(request)
        self._cookie(response, self._sessions.cookie_name(), session, True, secure)
        self._cookie(
            response, self._sessions.csrf_cookie_name(), csrf, False, secure
        )

    @staticmethod
    def _cookie(
        response: JSONResponse,
        name: str,
        value: str,
        httponly: bool,
        secure: bool,
    ) -> None:
        response.set_cookie(
            name,
            value,
            httponly=httponly,
            samesite="lax",
            secure=secure,
            max_age=12 * 3600,
        )

    @staticmethod
    def _secure(request: Request) -> bool:
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        return proto.lower() == "https"

    @staticmethod
    def _login_html() -> FileResponse:
        path = PackageRootFinder().find() / "dashboard" / "login.html"
        return FileResponse(path, media_type="text/html; charset=utf-8")
