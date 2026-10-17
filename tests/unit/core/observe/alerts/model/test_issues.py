"""ValidationReport helpers."""
from raft.core.observe.alerts.model.issues import ValidationReport
from tests.unit.base import RaftTestCase

class TestIssues(RaftTestCase):
    def test_public(self) -> None:
        r = ValidationReport()
        r.add_warning("w", "m")
        pub = r.to_public()
        assert pub["warnings"][0]["path"] == "w"
