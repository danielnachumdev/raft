"""``rbac.yaml`` schema: roles with permissions + subject bindings (#307)."""

from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from raft.core.core.errors.cta import OperatorError
from raft.core.core.rbac.binding import RbacBinding
from raft.core.core.rbac.permissions import PermissionCodes
from raft.core.core.rbac.role import RbacRole
from raft.core.core.rbac.subject import RbacSubject

RBAC_DOCUMENT_VERSION = 1


@dataclass(frozen=True)
class RbacDocument:
    """Versioned RBAC roles/bindings; missing file → empty (bootstrap elsewhere)."""

    version: int = RBAC_DOCUMENT_VERSION
    roles: Tuple[RbacRole, ...] = ()
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
        cls._validate_binding_roles(roles, bindings, path=path)
        return cls(version=version, roles=roles, bindings=bindings)

    def to_export(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "roles": [
                {"id": role.id, "permissions": list(role.permissions)}
                for role in self.roles
            ],
            "bindings": [
                {"subject": b.subject, "role": b.role} for b in self.bindings
            ],
        }

    def permissions_for(self, subject: str) -> frozenset[str]:
        key = RbacSubject.normalize(subject)
        if not key:
            return frozenset()
        role_ids = {
            RbacSubject.normalize(b.role)
            for b in self.bindings
            if RbacSubject.normalize(b.subject) == key
        }
        granted: set[str] = set()
        for role in self.roles:
            if RbacSubject.normalize(role.id) in role_ids:
                granted.update(role.permissions)
        return frozenset(granted)

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
    def _roles(cls, raw: Any, *, path: str) -> Tuple[RbacRole, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                f"{path} must be a list of role mappings.\n"
                f"Fix: set roles: [{{id: admin, permissions: ['*:read', '*:write']}}]",
                has_fix=False,
            )
        return tuple(
            cls._one_role(item, path=f"{path}[{index}]")
            for index, item in enumerate(raw)
        )

    @classmethod
    def _one_role(cls, raw: Any, *, path: str) -> RbacRole:
        if not isinstance(raw, Mapping):
            raise OperatorError(
                f"{path} must be a mapping.\n"
                f"Fix: use {{id: admin, permissions: ['*:read', '*:write']}}",
                has_fix=False,
            )
        role_id = str(raw.get("id") or "").strip()
        if not role_id:
            raise OperatorError(
                f"{path}.id must be a non-empty string.\n"
                f"Fix: set id on each role",
                has_fix=False,
            )
        perms = cls._permissions(raw.get("permissions"), path=f"{path}.permissions")
        return RbacRole(id=role_id, permissions=perms)

    @classmethod
    def _permissions(cls, raw: Any, *, path: str) -> Tuple[str, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                f"{path} must be a list of permission strings.\n"
                f"Fix: set permissions: ['firewall:read', '*:write']",
                has_fix=False,
            )
        out: list[str] = []
        for index, item in enumerate(raw):
            code = str(item or "").strip()
            if not code or not PermissionCodes.is_valid(code):
                raise OperatorError(
                    f"{path}[{index}] invalid permission {item!r}.\n"
                    f"Fix: use resource:read|write or *:read|*:write",
                    has_fix=False,
                )
            out.append(code)
        return tuple(out)

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
        subject = RbacSubject.normalize(str(raw.get("subject") or ""))
        role = str(raw.get("role") or "").strip()
        if not subject or not role:
            raise OperatorError(
                f"{path} requires subject and role.\n"
                f"Fix: set subject and role on each binding",
                has_fix=False,
            )
        return RbacBinding(subject=subject, role=role)

    @staticmethod
    def _validate_binding_roles(
        roles: Tuple[RbacRole, ...],
        bindings: Tuple[RbacBinding, ...],
        *,
        path: str,
    ) -> None:
        known = {RbacSubject.normalize(role.id) for role in roles}
        for binding in bindings:
            if RbacSubject.normalize(binding.role) not in known:
                raise OperatorError(
                    f"{path} binding role {binding.role!r} is not defined.\n"
                    f"Fix: add a roles entry with id: {binding.role}",
                    has_fix=False,
                )
