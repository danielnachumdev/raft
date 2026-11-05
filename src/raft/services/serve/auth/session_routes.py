"""Public session metadata for SPA logout + RBAC affordances."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from fastapi import FastAPI, Request

from raft.core.core.config.settings.dashboard_config import DashboardConfig

from .rbac_deps import ServeRbac


class DashboardSessionRoutes:
    """``GET /api/dashboard/session`` — mode, logout, RBAC snapshot."""

    def __init__(
        self,
        config: DashboardConfig,
        *,
        home: Optional[Path] = None,
        username_from_cookie: Optional[
            Callable[[Optional[str]], Optional[str]]
        ] = None,
    ) -> None:
        self._cfg = config
        self._rbac = (
            ServeRbac(
                home, config, username_from_cookie=username_from_cookie
            )
            if home is not None
            else None
        )

    def register(self, app: FastAPI) -> None:
        @app.get("/api/dashboard/session")
        def session(request: Request) -> Dict[str, Any]:
            return self._payload(request)

    def _payload(self, request: Request) -> Dict[str, Any]:
        mode = self._cfg.auth.mode
        out: Dict[str, Any] = {
            "mode": mode,
            "logout": self._logout(mode),
        }
        if self._rbac is not None:
            out["rbac"] = self._rbac.session_fields(request)
        return out

    def _logout(self, mode: str) -> Dict[str, str]:
        if mode == "password":
            return {"kind": "post", "path": "/api/dashboard/logout", "next": "/login"}
        if mode == "oauth":
            return {"kind": "navigate", "path": "/oauth2/sign_out?rd=/"}
        if mode == "external":
            return {
                "kind": "navigate",
                "path": self._cfg.auth.sign_in_url or "/",
            }
        return {"kind": "none", "path": "/"}
