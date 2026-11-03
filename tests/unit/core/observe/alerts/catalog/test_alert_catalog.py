"""AlertCatalog target options."""

from raft.core.observe.alerts.catalog.alert_catalog import AlertCatalog
from raft.core.observe.alerts.catalogs import AlertCatalogs
from tests.unit.base import RaftTestCase


class TestAlertCatalog(RaftTestCase):
    def test_build_includes_apps(self) -> None:
        cat = AlertCatalog.build(AlertCatalogs.default(), ["demo-api"])
        assert any(s["type_id"] == "metrics.http" for s in cat["sources"])
        opts = next(s for s in cat["sources"] if s["type_id"] == "control.events")
        values = {o["value"] for o in opts["select_fields"][0]["options"]}
        assert "-" in values and "demo-api" in values

    def test_build_includes_control_plane_and_each_service(self) -> None:
        cat = AlertCatalog.build(
            AlertCatalogs.default(),
            ["demo-api"],
            control_plane_names=["raft-router"],
        )
        status = next(
            s for s in cat["sources"] if s["type_id"] == "control.container_status"
        )
        opts = status["select_fields"][0]["options"]
        values = {o["value"]: o["label"] for o in opts}
        assert values["*"] == "Each service"
        assert "raft-router" in values
        assert "demo-api" in values
