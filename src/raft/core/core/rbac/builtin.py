"""Builtin RBAC roles that the host always exposes."""

from typing import Any, Mapping, MutableMapping, Tuple

from raft.core.core.rbac.permissions import WILDCARD_READ, WILDCARD_WRITE
from raft.core.core.rbac.role import RbacRole
from raft.core.core.rbac.subject import RbacSubject

ADMIN_ROLE_ID = "admin"


class BuiltinAdminRole:
    """Locked admin role with full wildcard grants."""

    id = ADMIN_ROLE_ID

    @classmethod
    def role(cls) -> RbacRole:
        return RbacRole(
            id=cls.id,
            permissions=(WILDCARD_READ, WILDCARD_WRITE),
        )

    @classmethod
    def is_admin(cls, role_id: str) -> bool:
        return RbacSubject.normalize(role_id) == RbacSubject.normalize(cls.id)

    @classmethod
    def ensure(cls, roles: Tuple[RbacRole, ...]) -> Tuple[RbacRole, ...]:
        admin = cls.role()
        others = tuple(role for role in roles if not cls.is_admin(role.id))
        return (admin, *others)

    @classmethod
    def normalize_mapping(cls, body: Mapping[str, Any]) -> dict[str, Any]:
        """Force builtin admin into a document mapping before validate/save."""
        out: MutableMapping[str, Any] = dict(body)
        raw_roles = out.get("roles")
        roles = list(raw_roles) if isinstance(raw_roles, list) else []
        kept = [item for item in roles if not cls._mapping_is_admin(item)]
        kept.insert(0, cls._admin_mapping())
        out["roles"] = kept
        return dict(out)

    @classmethod
    def _mapping_is_admin(cls, item: Any) -> bool:
        return isinstance(item, Mapping) and cls.is_admin(str(item.get("id") or ""))

    @classmethod
    def _admin_mapping(cls) -> dict[str, Any]:
        return {"id": cls.id, "permissions": [WILDCARD_READ, WILDCARD_WRITE]}
