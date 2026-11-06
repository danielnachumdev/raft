"""RbacAllowlistSync derives oauth allowlist from RBAC."""

from pathlib import Path

import yaml

from raft.core.core.rbac.document import RbacDocument
from raft.core.lifecycle.dashboard.rbac_allowlist_sync import RbacAllowlistSync
from tests.unit.base import RaftTestCase

_RBAC = {
    "version": 1,
    "roles": [{"id": "admin", "permissions": ["*:read", "*:write"]}],
    "bindings": [{"subject": "ops@example.com", "role": "admin"}],
}


class TestRbacAllowlistSync(RaftTestCase):
    def test_skips_when_not_oauth(self) -> None:
        home = Path(self.tmp_path)
        self._settings(home, mode="password")
        out = RbacAllowlistSync(home).sync()
        assert out["synced"] is False

    def test_writes_allowlist_when_oauth_and_rbac(self) -> None:
        home = Path(self.tmp_path)
        self._settings(home, mode="oauth")
        (home / "host" / "rbac.yaml").write_text(
            yaml.safe_dump(_RBAC), encoding="utf-8"
        )
        out = RbacAllowlistSync(home).sync()
        assert out["synced"] is True
        assert out["count"] == 1
        path = home / "host" / "secrets" / "dashboard" / "oauth-allowlist.txt"
        assert "ops@example.com" in path.read_text(encoding="utf-8")


    def test_sync_from_document_override(self) -> None:
        home = Path(self.tmp_path)
        self._settings(home, mode="oauth")
        doc = RbacDocument.from_mapping(_RBAC, path="host/rbac.yaml")
        out = RbacAllowlistSync(home).sync(doc)
        assert out["synced"] is True

    @staticmethod
    def _settings(home: Path, *, mode: str) -> None:
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text(
            yaml.safe_dump({"dashboard": {"auth": {"mode": mode}}}),
            encoding="utf-8",
        )
