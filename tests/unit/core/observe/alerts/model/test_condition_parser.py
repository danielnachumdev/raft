"""ConditionParser validation paths."""

import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.model.condition_parser import ConditionParser
from tests.unit.base import RaftTestCase


class TestConditionParser(RaftTestCase):
    def test_group_and_leaf_errors(self) -> None:
        p = ConditionParser()
        with pytest.raises(OperatorError):
            p.parse({"all": [], "extra": 1})
        rep = p.validate({"signal": "", "kind": "", "select": 1, "params": 1})
        assert not rep.ok

    def test_depth_and_leaves(self) -> None:
        deep = {"all": [{"all": [{"all": [{"all": [{"all": [{"all": [{"signal": "s", "kind": "k"}]}]}]}]}]}]}
        rep = ConditionParser().validate(deep)
        assert any("depth" in e.message for e in rep.errors)
