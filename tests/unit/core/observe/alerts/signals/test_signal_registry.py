"""SignalRegistry."""
import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.signals.metrics.http_source import HttpMetricSource
from raft.core.observe.alerts.signals.signal_registry import SignalRegistry
from tests.unit.base import RaftTestCase

class TestSignalRegistry(RaftTestCase):
    def test_duplicate_and_unknown(self) -> None:
        reg = SignalRegistry()
        reg.register(HttpMetricSource())
        with pytest.raises(ValueError):
            reg.register(HttpMetricSource())
        with pytest.raises(OperatorError):
            reg.get("nope")
