"""Permission catalog matching (#307)."""

from raft.core.core.rbac import PermissionCodes, WILDCARD_READ, WILDCARD_WRITE
from tests.unit.base import RaftTestCase


class TestPermissionCodes(RaftTestCase):
    def test_catalog_includes_wildcards_and_resources(self) -> None:
        catalog = PermissionCodes.catalog()
        assert WILDCARD_READ in catalog
        assert WILDCARD_WRITE in catalog
        assert "firewall:read" in catalog
        assert "rbac:write" in catalog

    def test_matches_exact_and_wildcards(self) -> None:
        assert PermissionCodes.matches("firewall:read", "firewall:read")
        assert PermissionCodes.matches(WILDCARD_READ, "alerts:read")
        assert PermissionCodes.matches(WILDCARD_WRITE, "runtime:write")
        assert not PermissionCodes.matches(WILDCARD_READ, "runtime:write")
        assert not PermissionCodes.matches("firewall:read", "alerts:read")

    def test_allows_any_grant(self) -> None:
        granted = frozenset({"firewall:read", WILDCARD_WRITE})
        assert PermissionCodes.allows(granted, "firewall:read")
        assert PermissionCodes.allows(granted, "settings:write")
        assert not PermissionCodes.allows(granted, "settings:read")

    def test_is_valid_shapes(self) -> None:
        assert PermissionCodes.is_valid("firewall:read")
        assert PermissionCodes.is_valid(WILDCARD_READ)
        assert not PermissionCodes.is_valid("nocolon")
        assert not PermissionCodes.is_valid(":read")
        assert not PermissionCodes.is_valid("firewall:execute")
