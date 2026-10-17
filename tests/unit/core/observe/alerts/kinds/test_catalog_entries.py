"""Kind catalog_entry helpers."""

from raft.core.observe.alerts.kinds import catalog_entries as ce
from tests.unit.base import RaftTestCase


class TestKindCatalogEntries(RaftTestCase):
    def test_threshold_fields(self) -> None:
        entry = ce.threshold_catalog("threshold")
        assert entry["fields"][0]["key"] == "aggregate"

    def test_event_count_and_state(self) -> None:
        assert ce.event_count_catalog("event_count")["value_types"] == ["event"]
        assert ce.state_match_catalog("state")["label"] == "State match"
