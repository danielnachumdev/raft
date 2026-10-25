"""Inbox item id helpers and public shape."""

from raft.core.observe.inbox import InboxItem, inbox_item_id, parse_inbox_item_id
from tests.unit.base import RaftTestCase


class TestInboxItem(RaftTestCase):
    def test_parse_ids(self) -> None:
        assert inbox_item_id("firewall-recommendation", "default-deny") == (
            "firewall-recommendation:default-deny"
        )
        assert parse_inbox_item_id("a:b") == ("a", "b")
        assert parse_inbox_item_id("nocolon") is None
        assert parse_inbox_item_id(":only") is None
        assert parse_inbox_item_id("only:") is None

    def test_public_and_unread(self) -> None:
        item = InboxItem(
            id="firewall-recommendation:default-deny",
            source="firewall-recommendation",
            source_item_id="default-deny",
            title="Default deny",
            summary="Deny any",
            severity="attention",
            href="/settings/edge-access#firewall-recommendations",
            dismissible=True,
            unread=True,
        )
        public = item.to_public()
        assert public["href"].endswith("#firewall-recommendations")
        assert public["unread"] is True
        assert item.with_unread(False).unread is False
