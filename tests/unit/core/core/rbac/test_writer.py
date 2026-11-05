"""RBAC document writer (#307)."""

from pathlib import Path

from raft.core.core.rbac.builtin import ADMIN_ROLE_ID
from raft.core.core.rbac.permissions import WILDCARD_READ, WILDCARD_WRITE
from raft.core.core.rbac.writer import RbacDocumentWriter
from tests.unit.base import RaftTestCase


class TestRbacDocumentWriter(RaftTestCase):
    def test_replace_and_export(self) -> None:
        home = Path(self.tmp_path)
        writer = RbacDocumentWriter(home)
        exported = writer.export_document()
        assert exported["roles"][0]["id"] == ADMIN_ROLE_ID
        assert exported["roles"][0]["permissions"] == [
            WILDCARD_READ,
            WILDCARD_WRITE,
        ]
        out = writer.replace(
            {
                "version": 1,
                "roles": [
                    {"id": "admin", "permissions": ["*:read", "*:write"]},
                ],
                "bindings": [{"subject": "ops@example.com", "role": "admin"}],
            }
        )
        assert out["document"]["bindings"][0]["subject"] == "ops@example.com"
        assert "temporary_override" in out["gitops"]
        assert writer.export_document()["roles"][0]["id"] == "admin"

    def test_replace_restores_builtin_admin(self) -> None:
        writer = RbacDocumentWriter(Path(self.tmp_path))
        out = writer.replace(
            {
                "version": 1,
                "roles": [{"id": "viewer", "permissions": ["status:read"]}],
                "bindings": [{"subject": "ops@example.com", "role": "viewer"}],
            }
        )
        role_ids = [role["id"] for role in out["document"]["roles"]]
        assert role_ids[0] == ADMIN_ROLE_ID
        assert "viewer" in role_ids

    def test_encode_decode_yaml_round_trip(self) -> None:
        writer = RbacDocumentWriter(Path(self.tmp_path))
        encoded = writer.encode_yaml(
            {
                "version": 1,
                "roles": [{"id": "viewer", "permissions": ["logs:read"]}],
                "bindings": [{"subject": "ops@example.com", "role": "viewer"}],
            }
        )
        assert "roles:" in encoded["yaml"]
        assert encoded["document"]["roles"][0]["id"] == ADMIN_ROLE_ID
        decoded = writer.decode_yaml(encoded["yaml"])
        assert decoded["document"]["bindings"][0]["subject"] == "ops@example.com"
