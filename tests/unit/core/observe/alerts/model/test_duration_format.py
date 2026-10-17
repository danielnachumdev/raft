"""AlertDuration format and required."""
import pytest
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.model.duration import AlertDuration
from tests.unit.base import RaftTestCase

class TestDurationFormat(RaftTestCase):
    def test_format_units(self) -> None:
        assert AlertDuration.format(86400) == "1d"
        assert AlertDuration.format(3600) == "1h"
        assert AlertDuration.format(60) == "1m"
        assert AlertDuration.format(7) == "7s"

    def test_required(self) -> None:
        with pytest.raises(OperatorError):
            AlertDuration.parse(None, path="p", default=None)
