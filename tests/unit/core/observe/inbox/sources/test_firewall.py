"""FirewallInboxSource maps recommendation rows to inbox items."""

from unittest.mock import MagicMock

from raft.core.observe.inbox.sources.firewall import (
    HREF,
    SOURCE_ID,
    FirewallInboxSource,
)
from tests.unit.base import RaftTestCase


class TestFirewallInboxSource(RaftTestCase):
    def test_maps_and_skips_non_dicts(self) -> None:
        recs = MagicMock()
        recs.list_public.return_value = {
            "recommendations": [
                {
                    "id": "permit-port-80",
                    "title": "Permit edge port 80",
                    "summary": "Allow HTTP",
                },
                "skip-me",
                {"id": "", "title": "blank"},
            ]
        }
        source = FirewallInboxSource(self.tmp_path, recommendations=recs)
        items = source.list_items()
        assert len(items) == 2
        assert items[0].id == f"{SOURCE_ID}:permit-port-80"
        assert items[0].href == HREF
        assert items[0].dismissible is True
        source.dismiss("permit-port-80")
        recs.dismiss.assert_called_once_with("permit-port-80")
