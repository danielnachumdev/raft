"""Attach auth middleware + login routes to the Serve FastAPI app."""

from typing import Optional

from fastapi import FastAPI

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.db.dashboard_sessions import DashboardSessionStore
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.dashboard.rbac_allowlist_sync import RbacAllowlistSync

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
        self._passwords: Optional[PasswordSessionAuth] = None
        self._store: Optional[DashboardSessionStore] = None

    def apply(self, app: FastAPI) -> None:
        cfg = self._resolve_config()
        home = self._stack.root
        app.state.raft_home = home
        self._store = DashboardSessionStore(home)
        app.state.dashboard_sessions = self._store
        RbacAllowlistSync(home).sync()
        if cfg.auth.mode == "password":
            self._wire_password(app, cfg)
        DashboardSessionRoutes(cfg, home=home, store=self._store).register(app)
        self._register_middleware(app, cfg)

    def _register_middleware(self, app: FastAPI, cfg: DashboardConfig) -> None:
        # Last added = outermost. Auth must run before RBAC safety net.
        app.add_middleware(
            DashboardRbacMiddleware,
            home=self._stack.root,
            config=cfg,
        )
        if cfg.auth.mode == "none":
            return
        if cfg.auth.mode == "password" and self._passwords is None:
            return
        app.add_middleware(
            DashboardAuthMiddleware,
            config=cfg,
            home=self._stack.root,
            store=self._store,
        )

    def _resolve_config(self) -> DashboardConfig:
        if self._cfg is not None:
            return self._cfg
        return SettingsLoader().load(self._stack.root).dashboard

    def _wire_password(self, app: FastAPI, cfg: DashboardConfig) -> bool:
        users = cfg.auth.password_users()
        if not users:
            return False
        assert self._store is not None
        self._passwords = PasswordSessionAuth.from_hashes(
            self._stack.root,
            password_hash=cfg.auth.password_hash,
            users={u: h for u, h in users.items()},
        )
        DashboardLoginRoutes(
            self._passwords, self._store, home=self._stack.root
        ).register(app)
        return True
