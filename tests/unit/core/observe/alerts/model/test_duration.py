"""AlertDuration parse edges."""
import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.model.duration import AlertDuration
from tests.unit.base import RaftTestCase

class TestAlertDuration(RaftTestCase):
    def test_bad_values(self) -> None:
        with pytest.raises(OperatorError):
            AlertDuration.parse("nope", path="p")
        with pytest.raises(OperatorError):
            AlertDuration.parse(-1, path="p")
        with pytest.raises(OperatorError):
            AlertDuration.parse("999d", path="p", max_seconds=60)
