"""AlertRuleParser field validation."""
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.rule_parser import AlertRuleParser
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE

class TestRuleParserValidate(RaftTestCase):
    def _p(self):
        return AlertRuleParser(AlertCatalogs.default())

    def test_not_mapping(self) -> None:
        assert not self._p().validate([]).ok

    def test_bad_id_and_name(self) -> None:
        body = {**RULE, "id": "BAD ID", "name": ""}
        assert not self._p().validate(body).ok

    def test_bad_severity_and_nodata(self) -> None:
        body = {**RULE, "severity": "nope", "noData": "nope", "enabled": "yes"}
        assert not self._p().validate(body).ok

    def test_bad_channels(self) -> None:
        body = {**RULE, "channelIds": [1]}
        assert not self._p().validate(body).ok

    def test_missing_condition(self) -> None:
        body = dict(RULE)
        del body["condition"]
        assert not self._p().validate(body).ok

    def test_kind_mismatch(self) -> None:
        body = {**RULE, "condition": {**RULE["condition"], "kind": "state"}}
        assert not self._p().validate(body).ok
