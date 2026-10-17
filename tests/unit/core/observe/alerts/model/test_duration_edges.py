"""AlertDuration edge cases."""

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.alerts.model.duration import AlertDuration
from tests.unit.base import RaftTestCase


class TestDurationEdges(RaftTestCase):
    def test_defaults_and_range(self) -> None:
        assert AlertDuration.parse(None, path="p", default=5) == 5
        with pytest.raises(OperatorError):
            AlertDuration.parse(None, path="p")
        with pytest.raises(OperatorError):
            AlertDuration.parse(999999, path="p", max_seconds=10)
        with pytest.raises(OperatorError):
            AlertDuration.parse(True, path="p")
        with pytest.raises(OperatorError):
            AlertDuration.parse(1.5, path="p")
        with pytest.raises(OperatorError):
            AlertDuration.parse([], path="p")  # type: ignore[arg-type]

    def test_format(self) -> None:
        assert AlertDuration.format(86400) == "1d"
        assert AlertDuration.format(3600) == "1h"
        assert AlertDuration.format(60) == "1m"
        assert AlertDuration.format(7) == "7s"
