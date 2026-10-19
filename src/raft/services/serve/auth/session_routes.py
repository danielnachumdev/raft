"""Public session metadata for SPA logout affordances."""

from typing import Any, Dict

from fastapi import FastAPI

from raft.core.core.config.settings.dashboard_config import DashboardConfig


class DashboardSessionRoutes:
    """``GET /api/dashboard/session`` — mode + how to log out."""

    def __init__(self, config: DashboardConfig) -> None:
        self._cfg = config

    def register(self, app: FastAPI) -> None:
        @app.get("/api/dashboard/session")
        def session() -> Dict[str, Any]:
            return self._payload()

    def _payload(self) -> Dict[str, Any]:
        mode = self._cfg.auth.mode
        return {
            "mode": mode,
            "logout": self._logout(mode),
        }

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
