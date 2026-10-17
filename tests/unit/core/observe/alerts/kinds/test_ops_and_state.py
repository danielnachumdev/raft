
"""Aggregates, operators, state, event_count kinds."""

from datetime import datetime, timezone, timedelta
from raft.core.observe.alerts.kinds.aggregates import Aggregates
from raft.core.observe.alerts.kinds.operators import Comparison
from raft.core.observe.alerts.kinds.state_match import StateMatchKind
from raft.core.observe.alerts.kinds.event_count import EventCountKind
from raft.core.observe.alerts.signals.series import SignalPoint, SubjectSeries
from tests.unit.base import RaftTestCase


class TestOpsAndState(RaftTestCase):
    def test_aggregates_and_ops(self) -> None:
        vals = [1.0, 2.0, 3.0]
        assert Aggregates.apply("min", vals) == 1.0
        assert Aggregates.apply("max", vals) == 3.0
        assert Aggregates.apply("sum", vals) == 6.0
        assert Aggregates.apply("last", vals) == 3.0
        assert Aggregates.apply("avg", []) is None
        assert Comparison.apply("lt", 1, 2)
        assert Comparison.apply("lte", 2, 2)
        assert Comparison.apply("eq", 1, 1)
        assert Comparison.apply("ne", 1, 2)
        assert Comparison.apply("gte", 2, 2)

    def test_state_and_events(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        series = SubjectSeries(
            "demo-web",
            (SignalPoint(now - timedelta(seconds=10), "exited"),),
        )
        result = StateMatchKind().evaluate(
            series, {"match": "notIn", "values": ["running"]}, now=now
        )
        assert result.matched is True
        events = SubjectSeries(
            "demo-api",
            tuple(SignalPoint(now - timedelta(seconds=i), "deployment") for i in range(5)),
        )
        counted = EventCountKind().evaluate(
            events, {"window": "1h", "op": "gte", "value": 5}, now=now
        )
        assert counted.matched is True
