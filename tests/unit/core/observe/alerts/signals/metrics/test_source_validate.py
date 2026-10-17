"""Metric source validate_select branches."""
from raft.core.observe.alerts.signals.metrics.http_source import HttpMetricSource
from raft.core.observe.alerts.signals.metrics.resources_source import ResourcesMetricSource
from tests.unit.base import RaftTestCase


class TestMetricSourceValidate(RaftTestCase):
    def test_http_validate_errors(self) -> None:
        src = HttpMetricSource()
        assert src.validate_select({}, path="s")
        assert src.validate_select({"target": "demo-api", "metric": "nope"}, path="s")
        issues = src.validate_select(
            {"target": "edge", "metric": "cpu_percent"}, path="s"
        )
        assert issues

    def test_resources_validate_errors(self) -> None:
        src = ResourcesMetricSource()
        assert src.validate_select({}, path="s")
        assert src.validate_select({"target": "demo-api", "metric": "nope"}, path="s")