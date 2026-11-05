"""RBAC enforcer story: missing file bootstraps; present file denies unbound (#307)."""

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


class TestRbacEnforcerStory(RaftTestCase):
    """Operator drops host/rbac.yaml; only bound subjects keep access.

    Scenario:
      1) Absent rbac.yaml → bootstrap allow for any subject.
      2) Present document → ops@example.com may write; stranger is denied.
      3) Missing permissions_for / failed store load → empty grant set.
    """

    def test_missing_file_bootstraps_full_admin(self) -> None:
        decision = RbacEnforcer(Path(self.tmp_path)).check(
            "ops@example.com", "runtime:write"
        )
        assert decision.allowed is True
        assert decision.bootstrap is True

    def test_present_file_allows_bound_denies_stranger(self) -> None:
        enforcer = self._enforcer_with_admin_doc()
        ok = enforcer.require("Ops@Example.com", "firewall:write")
        assert ok.allowed and not ok.bootstrap
        assert enforcer.permissions_for(None) == frozenset()
        assert not enforcer.check("other@example.com", "firewall:write").allowed
        with pytest.raises(PermissionError, match="RBAC denied"):
            enforcer.require("other@example.com", "firewall:write")
        assert enforcer.admitted("ops@example.com")
        assert not enforcer.admitted("other@example.com")
        assert enforcer.document() is not None

    def test_permissions_empty_without_binding_or_store(self) -> None:
        home = Path(self.tmp_path)
        assert RbacEnforcer(home).permissions_for("ops") == frozenset()
        enforcer = self._enforcer_with_admin_doc()
        with patch.object(enforcer._store, "load", return_value=None):
            assert enforcer.permissions_for("ops@example.com") == frozenset()

    def _enforcer_with_admin_doc(self) -> RbacEnforcer:
        home = Path(self.tmp_path)
        host = home / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "rbac.yaml").write_text(_RBAC_YAML, encoding="utf-8")
        return RbacEnforcer(home)
