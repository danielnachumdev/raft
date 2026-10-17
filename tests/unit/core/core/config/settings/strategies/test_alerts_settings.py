"""Alerts settings parser."""
import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.core.config.settings.strategies.alerts import AlertsSettingsParser
from tests.unit.base import RaftTestCase

class TestAlertsSettings(RaftTestCase):
    def test_defaults_and_errors(self) -> None:
        p = AlertsSettingsParser()
        assert p.parse(None).enabled is True
        with pytest.raises(OperatorError):
            p.parse([])
        with pytest.raises(OperatorError):
            p.parse({"intervalSeconds": 1})
