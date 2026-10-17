"""Rule parser nested condition validation."""
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestRuleParserGroup(RaftTestCase):
    def test_all_group_leaf_warnings(self) -> None:
        leaf = RULE["condition"]
        body = {
            **RULE,
            "condition": {"all": [leaf, {**leaf, "select": {"target": "", "metric": "nope"}}]},
        }
        rep = AlertRuleParser(AlertCatalogs.default()).validate(body)
        assert not rep.ok
        assert rep.warnings or rep.errors
