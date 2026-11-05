"""Authorize subjects against host ``rbac.yaml`` (#307)."""

from pathlib import Path

from raft.core.core.rbac.decision import RbacDecision
from raft.core.core.rbac.permissions import PermissionCodes
from raft.core.core.rbac.store import RbacStore
from raft.core.core.rbac.subject import RbacSubject


class RbacEnforcer:
    """Missing file → bootstrap allow; present file → deny-by-default."""

    def __init__(self, home: Path) -> None:
        self._store = RbacStore(home)

    def file_present(self) -> bool:
        return self._store.exists()

    def permissions_for(self, subject: str | None) -> frozenset[str]:
        if not self.file_present():
            return frozenset()
        doc = self._store.load()
        if doc is None:
            return frozenset()
        return doc.permissions_for(subject or "")

    def check(self, subject: str | None, permission: str) -> RbacDecision:
        if not self.file_present():
            return RbacDecision.allow_bootstrap()
        granted = self.permissions_for(subject)
        if PermissionCodes.allows(granted, permission):
            return RbacDecision.allow(granted)
        return RbacDecision.deny(granted)

    def require(self, subject: str | None, permission: str) -> RbacDecision:
        decision = self.check(subject, permission)
        if decision.allowed:
            return decision
        key = RbacSubject.normalize(subject or "") or "(anonymous)"
        raise PermissionError(
            f"RBAC denied {permission} for subject {key}.\n"
            f"Fix: bind the subject in host/rbac.yaml or grant {permission}"
        )
