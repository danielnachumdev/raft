"""Declarative FastAPI dependencies for RBAC authZ."""

from typing import Callable

from fastapi import HTTPException, Request

from raft.core.core.rbac import RbacEnforcer
from raft.core.core.rbac.permissions import Action, PermissionCodes


class RequirePermission:
    """``Depends(RequirePermission(\"metrics:read\"))`` — authZ after middleware authN."""

    def __init__(self, permission: str) -> None:
        if not PermissionCodes.is_valid(permission):
            raise ValueError(f"invalid permission code: {permission}")
        self._permission = permission

    def __call__(self, request: Request) -> str:
        subject = getattr(request.state, "rbac_subject", None) or ""
        home = getattr(request.app.state, "raft_home", None)
        if home is None:
            raise HTTPException(status_code=500, detail="RBAC home not configured")
        enforcer = RbacEnforcer(home)
        decision = enforcer.check(subject, self._permission)
        if decision.allowed:
            return subject
        raise HTTPException(
            status_code=403,
            detail=f"RBAC denied {self._permission}",
        )


def require_read(resource: str) -> RequirePermission:
    return RequirePermission(f"{resource}:{Action.READ}")


def require_write(resource: str) -> RequirePermission:
    return RequirePermission(f"{resource}:{Action.WRITE}")
