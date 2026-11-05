"""Builtin admin role normalization."""

from raft.core.core.rbac.builtin import ADMIN_ROLE_ID, BuiltinAdminRole
from raft.core.core.rbac.permissions import WILDCARD_READ, WILDCARD_WRITE
from raft.core.core.rbac.role import RbacRole
from tests.unit.base import RaftTestCase


class TestBuiltinAdminRole(RaftTestCase):
    def test_ensure_prepends_locked_admin(self) -> None:
        roles = BuiltinAdminRole.ensure(
            (
                RbacRole(id="viewer", permissions=("status:read",)),
                RbacRole(id="Admin", permissions=("*:read",)),
            )
        )
        assert roles[0].id == ADMIN_ROLE_ID
        assert roles[0].permissions == (WILDCARD_READ, WILDCARD_WRITE)
        assert [role.id for role in roles] == [ADMIN_ROLE_ID, "viewer"]

    def test_normalize_mapping_rewrites_admin_permissions(self) -> None:
        out = BuiltinAdminRole.normalize_mapping(
            {
                "version": 1,
                "roles": [
                    {"id": "admin", "permissions": ["status:read"]},
                    {"id": "viewer", "permissions": ["logs:read"]},
                ],
                "bindings": [{"subject": "ops@example.com", "role": "admin"}],
            }
        )
        assert out["roles"][0] == {
            "id": ADMIN_ROLE_ID,
            "permissions": [WILDCARD_READ, WILDCARD_WRITE],
        }
        assert out["roles"][1]["id"] == "viewer"
