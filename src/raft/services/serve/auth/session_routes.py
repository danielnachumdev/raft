"""Public session metadata for SPA logout + RBAC affordances."""

from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.db.dashboard_sessions import COOKIE_NAME, DashboardSessionStore
from raft.core.core.rbac import RbacEnforcer, RbacIdentity
from raft.core.core.rbac.identity import NONE_BOOTSTRAP_SUBJECT

from .cookies import DashboardSessionCookies
from .rbac_deps import ServeRbac


class DashboardSessionRoutes:
    """``GET /api/dashboard/session`` — mode, logout, RBAC snapshot."""

    def __init__(
        self,
        config: DashboardConfig,
        *,
        home: Path,
        store: DashboardSessionStore,
    ) -> None:
        self._cfg = config
        self._store = store
        self._rbac = ServeRbac(home, config)
        self._enforcer = RbacEnforcer(home)
        self._identity = RbacIdentity(config)

    def register(self, app: FastAPI) -> None:
        @app.get("/api/dashboard/session")
        def session(request: Request):
            return self._session(request)

        @app.post("/api/dashboard/logout")
        def logout(request: Request) -> JSONResponse:
            return self._logout(request)

    def _session(self, request: Request) -> Any:
        mode = self._cfg.auth.mode
        subject, minted = self._resolve_subject(request)
        body: Dict[str, Any] = {
            "mode": mode,
            "logout": self._logout_hint(mode),
            "identity": subject,
            "rbac": self._rbac.session_fields_for(subject),
        }
        if minted is None:
            return body
        response = JSONResponse(body)
        DashboardSessionCookies.attach(request, response, minted)
        return response

    def _resolve_subject(self, request: Request):
        existing = getattr(request.state, "rbac_subject", None)
        if existing:
            return existing, None
        cookie = request.cookies.get(COOKIE_NAME)
        subject = self._store.subject_for(cookie)
        if subject:
            return subject, None
        mode = self._cfg.auth.mode
        if mode == "none":
            return NONE_BOOTSTRAP_SUBJECT, None
        if mode in {"oauth", "external"}:
            header_subject = self._identity.from_headers(request.headers)
            if header_subject and self._enforcer.admitted(header_subject):
                minted = self._store.create(header_subject, auth_mode=mode)
                return header_subject, minted
        return "", None

    def _logout(self, request: Request) -> JSONResponse:
        cookie = request.cookies.get(COOKIE_NAME)
        self._store.revoke(cookie)
        next_url = self._logout_hint(self._cfg.auth.mode).get("next") or "/"
        response = JSONResponse({"ok": True, "next": next_url})
        DashboardSessionCookies.clear(response)
        return response

    def _logout_hint(self, mode: str) -> Dict[str, str]:
        if mode == "password":
            return {"kind": "post", "path": "/api/dashboard/logout", "next": "/login"}
        if mode == "oauth":
            return {
                "kind": "post",
                "path": "/api/dashboard/logout",
                "next": "/oauth2/sign_out?rd=/",
            }
        if mode == "external":
            return {
                "kind": "post",
                "path": "/api/dashboard/logout",
                "next": self._cfg.auth.sign_in_url or "/",
            }
        return {"kind": "none", "path": "/"}
