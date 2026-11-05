"""RBAC document writer (#307)."""

from pathlib import Path

from raft.core.core.rbac.writer import RbacDocumentWriter
from tests.unit.base import RaftTestCase


class TestRbacDocumentWriter(RaftTestCase):
    def test_replace_and_export(self) -> None:
        home = Path(self.tmp_path)
        writer = RbacDocumentWriter(home)
        assert writer.export_document()["roles"] == []
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
