"""AlertRuleParser validation branches."""

from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestRuleParserEdges(RaftTestCase):
    def _parser(self) -> AlertRuleParser:
        return AlertRuleParser(AlertCatalogs.default())

    def test_basics_and_timing(self) -> None:
        p = self._parser()
        bad = {"id": "BAD", "condition": RULE["condition"]}
        rep = p.validate(bad, path="r")
        assert not rep.ok
        rep2 = p.validate({**RULE, "repeatEvery": "1m"}, path="r")
        assert not rep2.ok

    def test_unknown_signal(self) -> None:
        body = {**RULE, "condition": {**RULE["condition"], "signal": "nope"}}
        assert not self._parser().validate(body).ok
