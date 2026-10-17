"""Rule parser warning merge on grouped leaves."""
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestRuleParserWarn(RaftTestCase):
    def test_group_with_bad_child_select(self) -> None:
        leaf = RULE["condition"]
        body = {
            **RULE,
            "channelIds": ["ops"],
            "condition": {
                "all": [
                    leaf,
                    {**leaf, "select": {"target": "demo-api", "metric": "bad-metric"}},
                ]
            },
        }
        rep = AlertRuleParser(AlertCatalogs.default()).validate(body)
        assert not rep.ok

    def test_validate_leaves_non_mapping(self) -> None:
        p = AlertRuleParser(AlertCatalogs.default())
        report = p.validate({**RULE, "condition": {"all": [RULE["condition"], "x"]}})
        assert not report.ok