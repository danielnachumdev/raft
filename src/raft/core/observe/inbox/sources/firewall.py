"""Inbox source: pending ordered-firewall recommendations."""

from pathlib import Path
from typing import List, Optional

from raft.core.lifecycle.firewall.recommendations import FirewallRecommendations
from raft.core.observe.inbox.item import InboxItem, inbox_item_id
from raft.core.observe.inbox.sources.base import InboxSource

SOURCE_ID = "firewall-recommendation"
HREF = "/settings/edge-access#firewall-recommendations"


class FirewallInboxSource(InboxSource):
    """Surfaces unset firewall baseline recommendations as attention items."""

    def __init__(
        self,
        home: Path,
        *,
        recommendations: Optional[FirewallRecommendations] = None,
    ) -> None:
        self._recs = recommendations or FirewallRecommendations(home)

    @property
    def source_id(self) -> str:
        return SOURCE_ID

    def list_items(self) -> List[InboxItem]:
        payload = self._recs.list_public()
        items = payload.get("recommendations") or []
        return [self._to_item(raw) for raw in items if isinstance(raw, dict)]

    def dismiss(self, source_item_id: str) -> None:
        self._recs.dismiss(source_item_id)

    def _to_item(self, raw: dict) -> InboxItem:
        source_item_id = str(raw.get("id") or "").strip()
        return InboxItem(
            id=inbox_item_id(SOURCE_ID, source_item_id),
            source=SOURCE_ID,
            source_item_id=source_item_id,
            title=str(raw.get("title") or source_item_id),
            summary=str(raw.get("summary") or ""),
            severity="attention",
            href=HREF,
            dismissible=True,
            unread=True,
        )
