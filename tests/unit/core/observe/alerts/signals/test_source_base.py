"""SignalSource default catalog/describe."""

from raft.core.observe.alerts.signals.series import ValueType
from raft.core.observe.alerts.signals.signal_source import SignalSource
from tests.unit.base import RaftTestCase


class Tiny(SignalSource):
    @property
    def type_id(self) -> str:
        return "tiny.signal"

    @property
    def value_type(self) -> ValueType:
        return ValueType.NUMERIC

    def validate_select(self, select, *, path):
        return []

    def query(self, select, *, window_seconds, ctx):
        return []


class TestSignalSourceBase(RaftTestCase):
    def test_defaults(self) -> None:
        src = Tiny()
        assert src.catalog_entry()["type_id"] == "tiny.signal"
        assert src.describe({}) == "tiny.signal"
