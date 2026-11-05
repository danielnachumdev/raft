"""Who may enter the dashboard given an RBAC document (#admission SoT)."""

from typing import Tuple

from raft.core.core.rbac.document import RbacDocument
from raft.core.core.rbac.subject import RbacSubject


class RbacAdmission:
    """Admit subjects bound to a role that grants at least one permission."""

    @classmethod
    def subjects(cls, document: RbacDocument) -> Tuple[str, ...]:
        granted = {
            RbacSubject.normalize(role.id): bool(role.permissions)
            for role in document.roles
        }
        out: list[str] = []
        seen: set[str] = set()
        for binding in document.bindings:
            subject = RbacSubject.normalize(binding.subject)
            role = RbacSubject.normalize(binding.role)
            if not subject or not granted.get(role):
                continue
            if subject in seen:
                continue
            seen.add(subject)
            out.append(subject)
        return tuple(out)

    @classmethod
    def allows(cls, document: RbacDocument, subject: str | None) -> bool:
        key = RbacSubject.normalize(subject or "")
        if not key:
            return False
        return key in set(cls.subjects(document))

    @classmethod
    def lines_for_allowlist(cls, document: RbacDocument) -> list[str]:
        return list(cls.subjects(document))
