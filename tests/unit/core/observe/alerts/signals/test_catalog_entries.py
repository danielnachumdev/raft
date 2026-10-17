"""Signal catalog_entry helpers."""

from raft.core.observe.alerts.signals import catalog_entries as ce
from raft.core.observe.alerts.signals.metrics.metric_keys import HTTP_METRICS
from tests.unit.base import RaftTestCase


class TestSignalCatalogEntries(RaftTestCase):
    def test_metric_and_container(self) -> None:
        m = ce.metric_source_catalog(type_id="m", label="L", metrics=HTTP_METRICS)
        assert m["select_fields"][1]["key"] == "metric"
        c = ce.container_status_catalog("control.container_status")
        assert c["value_type"] == "state"

    def test_graph_events(self) -> None:
        g = ce.graph_events_catalog("control.events")
        assert g["select_fields"][1]["key"] == "eventKind"
