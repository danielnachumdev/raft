"""Outcome of one RBAC permission check."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RbacDecision:
    """Outcome of one permission check."""

    allowed: bool
    bootstrap: bool
    permissions: frozenset[str]

    @classmethod
    def allow_bootstrap(cls) -> "RbacDecision":
        return cls(allowed=True, bootstrap=True, permissions=frozenset())

    @classmethod
    def allow(cls, permissions: frozenset[str]) -> "RbacDecision":
        return cls(allowed=True, bootstrap=False, permissions=permissions)

    @classmethod
    def deny(cls, permissions: frozenset[str]) -> "RbacDecision":
        return cls(allowed=False, bootstrap=False, permissions=permissions)
