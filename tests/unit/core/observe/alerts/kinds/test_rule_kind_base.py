"""RuleKind default window."""
from raft.core.observe.alerts.kinds.threshold import ThresholdKind
from tests.unit.base import RaftTestCase

class TestRuleKindBase(RaftTestCase):
    def test_window_default(self) -> None:
        assert ThresholdKind().window_seconds({}) >= 0
