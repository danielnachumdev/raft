"""FastAPI helpers for RBAC checks on serve routes."""

from pathlib import Path
from typing import Callable

from fastapi import HTTPException, Request

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.rbac import RbacEnforcer


class ServeRbac:
    """Resolve subject + enforce a permission for the current request."""

    def __init__(self, home: Path, config: DashboardConfig) -> None:
        self._home = home
        self._config = config
        self._enforcer = RbacEnforcer(home)

    def subject(self, request: Request) -> str:
        return getattr(request.state, "rbac_subject", None) or ""

    def session_fields(self, request: Request) -> dict:
        return self.session_fields_for(self.subject(request))

    def session_fields_for(self, subject: str) -> dict:
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
