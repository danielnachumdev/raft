"""More AlertRuleParser validation branches."""

from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestRuleParserMore(RaftTestCase):
    def test_basics_and_timing(self) -> None:
        p = AlertRuleParser(AlertCatalogs.default())
        r = RULE
        assert not p.validate("x").ok
        assert any("id" in i.path for i in p.validate({**r, "id": "BAD"}).errors)
        assert any("severity" in i.path for i in p.validate({**r, "severity": "x"}).errors)
        assert any("noData" in i.path for i in p.validate({**r, "noData": "x"}).errors)
        assert any("enabled" in i.path for i in p.validate({**r, "enabled": "y"}).errors)
        assert any(
            "channelIds" in i.path for i in p.validate({**r, "channelIds": [1]}).errors
        )
        assert any(
            "repeatEvery" in i.path for i in p.validate({**r, "repeatEvery": "1m"}).errors
        )

    def test_name_description_for(self) -> None:
        p = AlertRuleParser(AlertCatalogs.default())
        r = RULE
        assert any("name" in i.path for i in p.validate({**r, "name": "x" * 200}).errors)
        assert any(
            "description" in i.path
            for i in p.validate({**r, "description": "y" * 5000}).errors
        )
        assert any("for" in i.path for i in p.validate({**r, "for": "999d"}).errors)

    def test_unknown_signal_kind(self) -> None:
        p = AlertRuleParser(AlertCatalogs.default())
        bad_sig = {
            **RULE,
            "condition": {
                "signal": "nope",
                "select": {"target": "x"},
                "kind": "threshold",
                "params": {"aggregate": "avg", "window": "5m", "op": "gt", "value": 1},
            },
        }
        assert any("signal" in i.path for i in p.validate(bad_sig).errors)
        bad_kind = {
            **RULE,
            "condition": {**RULE["condition"], "kind": "nope", "params": {}},
        }
        assert any("kind" in i.path for i in p.validate(bad_kind).errors)
