"""Firewall document + rule validation."""

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.firewall import FirewallDocument, FirewallRule
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import rule_dict


class TestFirewallDocument(RaftTestCase):
    def test_round_trip(self) -> None:
        doc = FirewallDocument.from_mapping(
            {"version": 1, "rules": [rule_dict("lab", port=443)]}, path="fw"
        )
        assert doc.to_export()["rules"][0]["cidr"] == "192.0.2.0/24"
        assert doc.is_active()

    def test_rejects_bad_action(self) -> None:
        try:
            FirewallRule.from_mapping(rule_dict(action="maybe"), path="r")
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "deny, permit, or drop" in str(exc)

    def test_duplicate_ids(self) -> None:
        try:
            FirewallDocument.from_mapping(
                {"rules": [rule_dict("a"), rule_dict("a", cidr="192.0.2.2")]},
                path="fw",
            )
            raise AssertionError("expected OperatorError")
        except OperatorError as exc:
            assert "duplicate id" in str(exc)

    def test_none_document(self) -> None:
        assert FirewallDocument.from_mapping(None, path="fw").rules == ()

    def test_bad_shapes(self) -> None:
        for raw in ([], {"version": "x"}, {"version": 2}, {"rules": {}}):
            try:
                FirewallDocument.from_mapping(raw, path="fw")
                raise AssertionError("expected OperatorError")
            except OperatorError:
                pass
