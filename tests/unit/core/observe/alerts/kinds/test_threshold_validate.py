"""ThresholdKind validate_params branches."""

from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from tests.unit.base import RaftTestCase


class TestThresholdValidate(RaftTestCase):
    def test_bad_aggregate_and_window(self) -> None:
        kind = ThresholdKind()
        issues = kind.validate_params({"aggregate": "nope", "window": "bad", "value": "x"}, path="p")
        assert len(issues) >= 2
