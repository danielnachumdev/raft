"""EventCountKind validation."""

from raft.core.observe.alerts.kinds.event_count import EventCountKind
from tests.unit.base import RaftTestCase


class TestEventCountValidate(RaftTestCase):
    def test_bad_params(self) -> None:
        issues = EventCountKind().validate_params({"op": "nope", "value": -1}, path="p")
        paths = {i.path for i in issues}
        assert "p.op" in paths and "p.value" in paths

    def test_catalog(self) -> None:
        assert EventCountKind().catalog_entry()["kind_id"] == "event_count"
