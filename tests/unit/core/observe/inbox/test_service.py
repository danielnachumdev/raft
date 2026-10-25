"""OperatorInboxService aggregation, read/unread, dismiss."""

from typing import List
from unittest.mock import MagicMock

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.inbox import (
    FirewallInboxSource,
    InboxItem,
    InboxSource,
    OperatorInboxService,
    inbox_item_id,
)
from raft.core.observe.inbox.sources.firewall import SOURCE_ID as FW_SOURCE
from tests.unit.base import RaftTestCase


class _StaticSource(InboxSource):
    def __init__(self, source_id: str, items: List[InboxItem]) -> None:
        self._id = source_id
        self._items = list(items)
        self.dismissed: List[str] = []

    @property
    def source_id(self) -> str:
        return self._id

    def list_items(self) -> List[InboxItem]:
        return list(self._items)

    def dismiss(self, source_item_id: str) -> None:
        self.dismissed.append(source_item_id)
        self._items = [
            item for item in self._items if item.source_item_id != source_item_id
        ]


class _NoDismissSource(InboxSource):
    @property
    def source_id(self) -> str:
        return "plain"

    def list_items(self) -> List[InboxItem]:
        return []


class TestOperatorInboxService(RaftTestCase):
    def _prep_edge(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )

    def test_firewall_feed_mark_read_and_href(self) -> None:
        self._prep_edge()
        svc = OperatorInboxService(self.tmp_path)
        payload = svc.list_public()
        ids = {item["id"] for item in payload["items"]}
        assert inbox_item_id(FW_SOURCE, "permit-port-80") in ids
        assert payload["unreadCount"] == len(payload["items"])
        assert payload["badgeSemantics"] == "unread"
        assert payload["items"][0]["href"].endswith("#firewall-recommendations")
        first = payload["items"][0]["id"]
        after = svc.mark_read([first])
        assert after["unreadCount"] == payload["unreadCount"] - 1
        unread_again = svc.mark_unread([first])
        assert unread_again["unreadCount"] == payload["unreadCount"]

    def test_multi_source_mark_all_and_dismiss(self) -> None:
        alert = self._alert_item()
        src = _StaticSource("alerts-recommendation", [alert])
        empty = MagicMock()
        empty.list_public.return_value = {"recommendations": []}
        fw = FirewallInboxSource(self.tmp_path, recommendations=empty)
        svc = OperatorInboxService(self.tmp_path, sources=[fw, src])
        assert svc.summary()["totalCount"] == 1
        assert svc.mark_all_read()["unreadCount"] == 0
        dismissed = svc.dismiss(alert.id)
        assert src.dismissed == ["any-service-oom"]
        assert dismissed["items"] == []

    def test_errors(self) -> None:
        svc = OperatorInboxService(self.tmp_path, sources=[])
        self._expect_error(lambda: svc.dismiss("nope"))
        self._expect_error(lambda: svc.dismiss("missing:x"))
        blocked = OperatorInboxService(
            self.tmp_path, sources=[_NoDismissSource()]
        )
        self._expect_error(lambda: blocked.dismiss("plain:x"))

    def _alert_item(self) -> InboxItem:
        return InboxItem(
            id="alerts-recommendation:any-service-oom",
            source="alerts-recommendation",
            source_item_id="any-service-oom",
            title="OOM alert",
            summary="Watch crash-loop",
            severity="attention",
            href="/settings/alerts#alert-recommendations",
            dismissible=True,
        )

    def _expect_error(self, fn) -> None:
        try:
            fn()
            raise AssertionError("expected OperatorError")
        except OperatorError:
            pass
