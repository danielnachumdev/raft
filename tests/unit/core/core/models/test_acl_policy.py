"""AclPolicy parse + CIDR validation."""

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.acl_policy import AclPolicy
from tests.unit.base import RaftTestCase


class TestAclPolicy(RaftTestCase):
    def test_off_default(self) -> None:
        policy = AclPolicy.from_mapping(None, path="acl.gate")
        assert policy.mode == "off"
        assert policy.entries == ()
        assert not policy.is_active()

    def test_whitelist_with_cidr(self) -> None:
        policy = AclPolicy.from_mapping(
            {
                "mode": "whitelist",
                "entries": [
                    {"id": "lab", "cidr": "192.0.2.0/24", "comment": "TEST-NET"},
                ],
            },
            path="acl.gate",
        )
        assert policy.is_active()
        assert policy.entries[0].cidr == "192.0.2.0/24"
        assert policy.to_public()["entries"][0]["id"] == "lab"

    def test_rejects_empty_whitelist(self) -> None:
        with pytest.raises(OperatorError, match="requires at least one"):
            AclPolicy.from_mapping({"mode": "whitelist", "entries": []}, path="acl.gate")

    def test_rejects_bad_cidr(self) -> None:
        with pytest.raises(OperatorError, match="not a valid IP"):
            AclPolicy.from_mapping(
                {
                    "mode": "blacklist",
                    "entries": [{"id": "bad", "cidr": "not-an-ip"}],
                },
                path="acl.gate",
            )

    def test_rejects_duplicate_ids(self) -> None:
        with pytest.raises(OperatorError, match="duplicate id"):
            AclPolicy.from_mapping(
                {
                    "mode": "blacklist",
                    "entries": [
                        {"id": "x", "cidr": "192.0.2.1"},
                        {"id": "x", "cidr": "192.0.2.2"},
                    ],
                },
                path="acl.gate",
            )
