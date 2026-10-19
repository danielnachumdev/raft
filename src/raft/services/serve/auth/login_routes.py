"""Password login / logout / auth-status routes for the dashboard."""

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .password_session import PasswordSessionAuth


class DashboardLoginRoutes:
    """Register ``/api/dashboard/*`` password endpoints."""

    def __init__(self, sessions: PasswordSessionAuth) -> None:
        self._sessions = sessions

    def register(self, app: FastAPI) -> None:
        sessions = self._sessions

        @app.get("/api/dashboard/auth")
        def auth_status(request: Request) -> Dict[str, Any]:
            cookie = request.cookies.get(sessions.cookie_name())
            return {
                "authenticated": sessions.session_ok(cookie),
                "mode": "password",
            }

        @app.post("/api/dashboard/login")
        async def login(request: Request):
            return await self._login(request)

        @app.post("/api/dashboard/logout")
        def logout() -> JSONResponse:
            return self._logout_response()

    async def _login(self, request: Request) -> JSONResponse:
        body = await request.json()
        password = str((body or {}).get("password") or "")
        tokens = self._sessions.login(password)
        if tokens is None:
            return JSONResponse({"detail": "invalid password"}, status_code=401)
        session, csrf = tokens
        response = JSONResponse({"ok": True})
        self._set_cookies(response, session, csrf)
        return response

    def _logout_response(self) -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(self._sessions.cookie_name())
        response.delete_cookie(self._sessions.csrf_cookie_name())
        return response

    def _set_cookies(self, response: JSONResponse, session: str, csrf: str) -> None:
        response.set_cookie(
            self._sessions.cookie_name(),
            session,
            httponly=True,
            samesite="lax",
            max_age=12 * 3600,
        )
        response.set_cookie(
            self._sessions.csrf_cookie_name(),
            csrf,
            httponly=False,
            samesite="lax",
            max_age=12 * 3600,
        )
