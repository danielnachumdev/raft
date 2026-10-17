"""ThresholdKind evaluation."""

from datetime import datetime, timezone, timedelta
from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from raft.core.observe.alerts.signals.series import SignalPoint, SubjectSeries
from tests.unit.base import RaftTestCase


class TestThresholdKind(RaftTestCase):
    def test_avg_gt(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        series = SubjectSeries(
            "demo-api",
            (
                SignalPoint(now - timedelta(seconds=60), 0.1),
                SignalPoint(now - timedelta(seconds=30), 0.2),
            ),
        )
        result = ThresholdKind().evaluate(
            series,
            {"aggregate": "avg", "window": "5m", "op": "gt", "value": 0.05},
            now=now,
        )
        assert result.matched is True
        assert abs(result.value - 0.15) < 1e-9

    def test_no_data(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        result = ThresholdKind().evaluate(
            SubjectSeries("demo-api", ()),
            {"aggregate": "avg", "window": "5m", "op": "gt", "value": 0.05},
            now=now,
        )
        assert result.matched is None
