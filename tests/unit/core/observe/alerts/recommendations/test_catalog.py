"""Default alert recommendation catalog coverage."""

from raft.core.observe.alerts.recommendations import AlertRecommendationCatalog
from raft.core.observe.ops.status.models import STATUS_CRASH_LOOPING
from tests.unit.base import RaftTestCase


class TestAlertRecommendationCatalog(RaftTestCase):
    def test_includes_oom_and_defaults(self) -> None:
        items = AlertRecommendationCatalog.candidates()
        ids = {item["id"] for item in items}
        assert ids == {
            "any-service-oom",
            "any-service-not-running",
            "any-service-high-memory",
        }
        oom = next(i for i in items if i["id"] == "any-service-oom")
        rule = oom["rule"]
        assert rule["channelIds"] == []
        assert rule["condition"]["signal"] == "control.container_status"
        assert rule["condition"]["select"] == {"target": "*"}
        assert rule["condition"]["kind"] == "state"
        assert STATUS_CRASH_LOOPING in rule["condition"]["params"]["values"]

    def test_high_memory_is_generic_threshold(self) -> None:
        item = next(
            i
            for i in AlertRecommendationCatalog.candidates()
            if i["id"] == "any-service-high-memory"
        )
        cond = item["rule"]["condition"]
        assert cond["signal"] == "metrics.resources"
        assert cond["select"] == {"target": "*", "metric": "memory_used_percent"}
        assert cond["kind"] == "threshold"
        assert cond["params"]["op"] == "gt"
        assert cond["params"]["value"] == 90

    def test_covers_by_id_and_leaf(self) -> None:
        oom = next(
            i
            for i in AlertRecommendationCatalog.candidates()
            if i["id"] == "any-service-oom"
        )
        assert AlertRecommendationCatalog.covers([{"id": "any-service-oom"}], oom)
        assert AlertRecommendationCatalog.covers(
            [{"id": "other", "condition": oom["rule"]["condition"]}], oom
        )
        assert not AlertRecommendationCatalog.covers(
            [{"id": "other", "condition": {"signal": "metrics.http"}}], oom
        )
        assert not AlertRecommendationCatalog.covers([{"id": "x"}], oom)

    def test_params_cover_superset_values(self) -> None:
        want = {"match": "in", "values": ["crash-looping"]}
        assert AlertRecommendationCatalog._params_cover(
            {"match": "in", "values": ["crash-looping", "exited"]}, want
        )
        assert not AlertRecommendationCatalog._params_cover(
            {"match": "in", "values": ["exited"]}, want
        )
        assert not AlertRecommendationCatalog._params_cover({"match": "notIn"}, want)
