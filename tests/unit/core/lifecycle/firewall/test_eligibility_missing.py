"""Firewall eligibility soft-fails missing applied manifests."""

from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.firewall.eligibility import FirewallEligibility

from tests.unit.base import RaftTestCase


class TestFirewallEligibilityMissing(RaftTestCase):
    def test_meta_soft_fails_when_app_yaml_missing(self) -> None:
        ghost = App(
            name="docket",
            public_host="docket.example.com",
            source="git",
            path="services/docket/checkout",
        )
        stack = Stack(root=self.tmp_path, apps=(ghost,))
        meta = FirewallEligibility(stack).meta("docket")
        assert meta["supported"] is False
        assert "missing" in meta["reason"]
