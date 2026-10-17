"""StateMatchKind validation and no data."""

from datetime import datetime, timezone
from raft.core.observe.alerts.kinds.state_match import StateMatchKind
from raft.core.observe.alerts.signals.series import SubjectSeries
from tests.unit.base import RaftTestCase


class TestStateMatchValidate(RaftTestCase):
    def test_validate_and_no_data(self) -> None:
        kind = StateMatchKind()
        issues = kind.validate_params({"match": "x", "values": []}, path="p")
        assert issues
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        res = kind.evaluate(SubjectSeries("demo-api", ()), {"match": "in", "values": ["x"]}, now=now)
        assert res.matched is None
