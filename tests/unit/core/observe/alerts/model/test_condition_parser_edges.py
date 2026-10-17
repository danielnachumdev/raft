"""ConditionParser depth and leaf limits."""
from raft.core.observe.alerts.model.condition_parser import ConditionParser
from tests.unit.base import RaftTestCase


class TestConditionParserEdges(RaftTestCase):
    def test_not_mapping_and_many_children(self) -> None:
        p = ConditionParser()
        rep = p.validate("not-a-map")
        assert not rep.ok
        many = {"all": [{"signal": "s", "kind": "k"} for _ in range(9)]}
        rep2 = p.validate(many)
        assert not rep2.ok
