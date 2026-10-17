"""AlertRulesDocument parsing errors."""

import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.model.document import AlertRulesDocument
from tests.unit.base import RaftTestCase
from tests.unit.core.observe.alerts.sample_rule import RULE


class TestAlertDocument(RaftTestCase):
    def test_empty_and_errors(self) -> None:
        regs = AlertCatalogs.default()
        assert AlertRulesDocument.from_mapping(None, registries=regs).rules == ()
        with pytest.raises(OperatorError):
            AlertRulesDocument.from_mapping([], registries=regs)
        with pytest.raises(OperatorError):
            AlertRulesDocument.from_mapping({"version": 9, "rules": []}, registries=regs)
        with pytest.raises(OperatorError):
            AlertRulesDocument.from_mapping({"version": 1, "rules": "bad"}, registries=regs)

    def test_duplicate_id(self) -> None:
        regs = AlertCatalogs.default()
        raw = {"version": 1, "rules": [RULE, RULE]}
        with pytest.raises(OperatorError):
            AlertRulesDocument.from_mapping(raw, registries=regs)
