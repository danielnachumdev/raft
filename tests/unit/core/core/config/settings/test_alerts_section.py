"""alerts: settings section."""

import pytest
from raft.core.core.config.settings.strategies.alerts import AlertsSettingsParser
from raft.core.core.errors.cta import OperatorError
from tests.unit.base import RaftTestCase


class TestAlertsSection(RaftTestCase):
    def test_defaults(self) -> None:
        cfg = AlertsSettingsParser().parse(None)
        assert cfg.enabled is True
        assert cfg.interval_seconds == 60.0

    def test_min_interval(self) -> None:
        with pytest.raises(OperatorError):
            AlertsSettingsParser().parse({"intervalSeconds": 5})
