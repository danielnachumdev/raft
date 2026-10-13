"""ACL v1 → ordered firewall migration."""

from raft.core.core.models.acl_policy import AclPolicy
from raft.core.core.models.firewall import AclV1Migrator
from raft.core.core.models.state.acl_store import AppAclStore
from tests.unit.base import RaftTestCase


class TestAclV1Migrator(RaftTestCase):
    def test_gate_whitelist_and_app_blacklist(self) -> None:
        self._write_acl()
        doc = AclV1Migrator(self.tmp_path, ports=(80, 443)).migrate()
        assert doc.source == "acl-v1-migrated"
        actions = {(r.service, r.action, r.port) for r in doc.rules}
        assert ("any", "permit", 80) in actions
        assert ("any", "deny", 80) in actions
        assert ("demo-api", "deny", 443) in actions

    def _write_acl(self) -> None:
        (self.tmp_path / "settings.yaml").write_text(
            "edge: {http: 80, https: 443}\n"
            "acl:\n  gate:\n    mode: whitelist\n"
            "    entries:\n      - id: lab\n        cidr: 192.0.2.0/24\n",
            encoding="utf-8",
        )
        AppAclStore(self.tmp_path).save(
            "demo-api",
            AclPolicy.from_mapping(
                {
                    "mode": "blacklist",
                    "entries": [{"id": "bad", "cidr": "198.51.100.10"}],
                },
                path="app",
            ),
        )
