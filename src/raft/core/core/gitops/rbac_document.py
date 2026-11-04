"""Minimal ``rbac.yaml`` schema stub for #307 / #317."""

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from raft.core.core.errors.cta import OperatorError

RBAC_DOCUMENT_VERSION = 1


@dataclass(frozen=True)
class RbacBinding:
    """One subject → role binding (schema stub)."""

    subject: str
    role: str


@dataclass(frozen=True)
class RbacDocument:
    """Versioned RBAC roles/bindings; missing file → empty."""

    version: int = RBAC_DOCUMENT_VERSION
    roles: Tuple[str, ...] = ()
    bindings: Tuple[RbacBinding, ...] = ()

    @classmethod
    def empty(cls) -> "RbacDocument":
        return cls()

    @classmethod
    def from_mapping(cls, raw: Any, *, path: str) -> "RbacDocument":
        if raw is None:
            return cls.empty()
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{version: 1, roles: [...], bindings: [...]}}",
                has_fix=False,
            )
        version = cls._version(raw.get("version"), path=f"{path}.version")
        roles = cls._roles(raw.get("roles"), path=f"{path}.roles")
        bindings = cls._bindings(raw.get("bindings"), path=f"{path}.bindings")
        return cls(version=version, roles=roles, bindings=bindings)

    def to_export(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "roles": list(self.roles),
            "bindings": [
                {"subject": b.subject, "role": b.role} for b in self.bindings
            ],
        }

    @staticmethod
    def _version(raw: Any, *, path: str) -> int:
        if raw is None:
            return RBAC_DOCUMENT_VERSION
        try:
            version = int(raw)
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"{path} must be an integer.\n"
                f"Fix: set version: {RBAC_DOCUMENT_VERSION}",
                has_fix=False,
            ) from exc
        if version != RBAC_DOCUMENT_VERSION:
            raise OperatorError(
                f"{path} unsupported version {version}.\n"
                f"Fix: use version: {RBAC_DOCUMENT_VERSION}",
                has_fix=False,
            )
        return version

    @classmethod
    def _roles(cls, raw: Any, *, path: str) -> Tuple[str, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                f"{path} must be a list of role name strings.\n"
                f"Fix: set roles: [admin, viewer]",
                has_fix=False,
            )
        roles = [str(item).strip() for item in raw]
        if any(not name for name in roles):
            raise OperatorError(
                f"{path} entries must be non-empty strings.\n"
                f"Fix: remove blank role names",
                has_fix=False,
            )
        return tuple(roles)

    @classmethod
    def _bindings(cls, raw: Any, *, path: str) -> Tuple[RbacBinding, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                f"{path} must be a list.\n"
                f"Fix: set bindings: [{{subject: ops@example.com, role: admin}}]",
                has_fix=False,
            )
        return tuple(
            cls._one_binding(item, path=f"{path}[{index}]")
            for index, item in enumerate(raw)
        )

    @staticmethod
    def _one_binding(raw: Any, *, path: str) -> RbacBinding:
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{subject: ops@example.com, role: admin}}",
                has_fix=False,
            )
        subject = str(raw.get("subject") or "").strip()
        role = str(raw.get("role") or "").strip()
        if not subject or not role:
            raise OperatorError(
                f"{path} requires subject and role.\n"
                f"Fix: set subject and role on each binding",
                has_fix=False,
            )
        return RbacBinding(subject=subject, role=role)
