"""RBAC enforcer bootstrap vs deny-by-default (#307)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.core.core.rbac import RbacEnforcer
from tests.unit.base import RaftTestCase

_RBAC_YAML = (
    "version: 1\n"
    "roles:\n"
    "  - id: admin\n"
    "    permissions: ['*:read', '*:write']\n"
    "bindings:\n"
    "  - subject: ops@example.com\n"
    "    role: admin\n"
)


class TestRbacEnforcer(RaftTestCase):
    def test_missing_file_bootstrap(self) -> None:
        home = Path(self.tmp_path)
        decision = RbacEnforcer(home).check("ops@example.com", "runtime:write")
        assert decision.allowed is True
        assert decision.bootstrap is True

    def test_present_unbound_denies(self) -> None:
        home = Path(self.tmp_path)
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "rbac.yaml").write_text(_RBAC_YAML, encoding="utf-8")
        enforcer = RbacEnforcer(home)
        ok = enforcer.require("Ops@Example.com", "firewall:write")
        assert ok.allowed and not ok.bootstrap
        assert enforcer.permissions_for(None) == frozenset()
        assert not enforcer.check("other@example.com", "firewall:write").allowed
        with pytest.raises(PermissionError, match="RBAC denied"):
            enforcer.require("other@example.com", "firewall:write")

    def test_missing_permissions_empty(self) -> None:
        assert RbacEnforcer(Path(self.tmp_path)).permissions_for("ops") == frozenset()

    def test_permissions_empty_when_store_load_none(self) -> None:
        home = Path(self.tmp_path)
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "rbac.yaml").write_text(_RBAC_YAML, encoding="utf-8")
        enforcer = RbacEnforcer(home)
        with patch.object(enforcer._store, "load", return_value=None):
            assert enforcer.permissions_for("ops@example.com") == frozenset()
