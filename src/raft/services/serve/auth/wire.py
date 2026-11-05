"""Attach auth middleware + login routes to the Serve FastAPI app."""

from typing import Optional

from fastapi import FastAPI

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.models.stack import Stack

from .login_routes import DashboardLoginRoutes
from .middleware import DashboardAuthMiddleware
from .password_session import PasswordSessionAuth
from .rbac_middleware import DashboardRbacMiddleware
from .session_routes import DashboardSessionRoutes


class ServeAuthWire:
    """Wire dashboard auth into :class:`ServeAppFactory`."""

    def __init__(self, stack: Stack, config: Optional[DashboardConfig] = None) -> None:
        self._stack = stack
        self._cfg = config
        self._sessions: Optional[PasswordSessionAuth] = None

    def apply(self, app: FastAPI) -> None:
        cfg = self._resolve_config()
        if cfg.auth.mode == "password":
            self._wire_password(app, cfg)
        username_fn = self._sessions.username if self._sessions else None
        self._register_session(app, cfg, username_fn)
        self._register_middleware(app, cfg, username_fn)

    def _register_session(self, app, cfg, username_fn) -> None:
        DashboardSessionRoutes(
            cfg,
            home=self._stack.root,
            username_from_cookie=username_fn,
        ).register(app)

    def _register_middleware(self, app, cfg, username_fn) -> None:
        # Last added = outermost. Auth must run before RBAC.
        app.add_middleware(
            DashboardRbacMiddleware,
            home=self._stack.root,
            config=cfg,
            username_from_cookie=username_fn,
        )
        if cfg.auth.mode == "none":
            return
        if cfg.auth.mode == "password" and self._sessions is None:
            return
        app.add_middleware(
            DashboardAuthMiddleware, config=cfg, sessions=self._sessions
        )

    def _resolve_config(self) -> DashboardConfig:
        if self._cfg is not None:
            return self._cfg
        return SettingsLoader().load(self._stack.root).dashboard

    def _wire_password(self, app: FastAPI, cfg: DashboardConfig) -> bool:
        users = cfg.auth.password_users()
        if not users:
            return False
        self._sessions = PasswordSessionAuth.from_hashes(
            self._stack.root,
            password_hash=cfg.auth.password_hash,
            users={u: h for u, h in users.items()},
        )
        DashboardLoginRoutes(self._sessions).register(app)
        return True
