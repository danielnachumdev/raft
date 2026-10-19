"""Attach auth middleware + login routes to the Serve FastAPI app."""

from typing import Optional

from fastapi import FastAPI

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.models.stack import Stack

from .login_routes import DashboardLoginRoutes
from .middleware import DashboardAuthMiddleware
from .password_session import PasswordSessionAuth
from .session_routes import DashboardSessionRoutes


class ServeAuthWire:
    """Wire dashboard auth into :class:`ServeAppFactory`."""

    def __init__(self, stack: Stack, config: Optional[DashboardConfig] = None) -> None:
        self._stack = stack
        self._cfg = config
        self._sessions: Optional[PasswordSessionAuth] = None

    def apply(self, app: FastAPI) -> None:
        cfg = self._resolve_config()
        if cfg.auth.mode == "none":
            return
        DashboardSessionRoutes(cfg).register(app)
        if cfg.auth.mode == "password":
            if not self._wire_password(app, cfg):
                return
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, sessions=self._sessions
        )

    def _resolve_config(self) -> DashboardConfig:
        if self._cfg is not None:
            return self._cfg
        from raft.core.core.config.settings import SettingsLoader

        return SettingsLoader().load(self._stack.root).dashboard

    def _wire_password(self, app: FastAPI, cfg: DashboardConfig) -> bool:
        if not cfg.auth.password_hash:
            return False
        self._sessions = PasswordSessionAuth(
            self._stack.root, password_hash=cfg.auth.password_hash
        )
        DashboardLoginRoutes(self._sessions).register(app)
        return True
