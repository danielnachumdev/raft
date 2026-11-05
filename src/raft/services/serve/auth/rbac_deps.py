"""FastAPI helpers for RBAC checks on serve routes."""

from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, Request

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.rbac import RbacEnforcer, RbacIdentity


class ServeRbac:
    """Resolve subject + enforce a permission for the current request."""

    def __init__(
        self,
        home: Path,
        config: DashboardConfig,
        *,
        username_from_cookie: Optional[
            Callable[[Optional[str]], Optional[str]]
        ] = None,
    ) -> None:
        self._home = home
        self._identity = RbacIdentity(config)
        self._enforcer = RbacEnforcer(home)
        self._username_from_cookie = username_from_cookie

    def subject(self, request: Request) -> str:
        username = getattr(request.state, "rbac_username", None)
        if username is None and self._username_from_cookie is not None:
            cookie = request.cookies.get("raft_dash_session")
            username = self._username_from_cookie(cookie)
        return self._identity.from_headers(request.headers, password_username=username)

    def session_fields(self, request: Request) -> dict:
        subject = self.subject(request)
        if not self._enforcer.file_present():
            return {
                "identity": subject,
                "bootstrap": True,
                "permissions": ["*:read", "*:write"],
            }
        granted = sorted(self._enforcer.permissions_for(subject))
        return {
            "identity": subject,
            "bootstrap": False,
            "permissions": granted,
        }

    def require(self, permission: str) -> Callable:
        def _dep(request: Request) -> str:
            subject = self.subject(request)
            decision = self._enforcer.check(subject, permission)
            if decision.allowed:
                request.state.rbac_subject = subject
                return subject
            raise HTTPException(
                status_code=403,
                detail=f"RBAC denied {permission}",
            )

        return _dep
