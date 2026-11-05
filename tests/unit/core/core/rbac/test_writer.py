"""RBAC document writer (#307)."""

from pathlib import Path

from raft.core.core.rbac.writer import RbacDocumentWriter
from tests.unit.base import RaftTestCase


class TestRbacDocumentWriter(RaftTestCase):
    def test_put_and_get(self) -> None:
        home = Path(self.tmp_path)
        writer = RbacDocumentWriter(home)
        assert writer.get()["roles"] == []
        out = writer.put(
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
        assert writer.get()["roles"][0]["id"] == "admin"
