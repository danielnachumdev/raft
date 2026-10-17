"""ConditionEvaluator combine / no_data branches."""

from raft.core.observe.alerts.catalogs import AlertCatalogs
from raft.core.observe.alerts.engine.condition_evaluator import ConditionEvaluator
from raft.core.observe.alerts.model.condition import ConditionLeaf
from tests.unit.base import RaftTestCase


class TestCombineNoData(RaftTestCase):
    def test_combine_all_any(self) -> None:
        ev = ConditionEvaluator(AlertCatalogs.default())
        assert ev._combine("all", [True, True]) is True
        assert ev._combine("all", [True, False]) is False
        assert ev._combine("all", [True, None]) is None
        assert ev._combine("any", [False, True]) is True
        assert ev._combine("any", [False, None]) is None
        assert ev._combine("any", [False, False]) is False

    def test_no_data_modes(self) -> None:
        ev = ConditionEvaluator(AlertCatalogs.default())
        assert ev._apply_no_data(True, "ok") is True
        assert ev._apply_no_data(None, "ok") is False
        assert ev._apply_no_data(None, "alerting") is True
        assert ev._apply_no_data(None, "keep") is None

    def test_child_value_paths(self) -> None:
        ev = ConditionEvaluator(AlertCatalogs.default())
        leaf = ConditionLeaf(
            "metrics.http",
            {"target": "demo-api", "metric": "requests"},
            "threshold",
            {},
        )
        m, _ = ev._child_value((["demo-api"], {"demo-api": True}, {}), "x", leaf)
        assert m is True
        wild = ConditionLeaf(
            "metrics.http", {"target": "*"}, "threshold", {}
        )
        assert ev._child_value((["a"], {"a": False}, {}), "b", wild) == (None, ())
