"""Inbox source: pending alert-setup recommendations (optional plugin)."""

from pathlib import Path
from typing import Any, List, Optional

from raft.core.observe.inbox.item import InboxItem, inbox_item_id
from raft.core.observe.inbox.sources.base import InboxSource

SOURCE_ID = "alerts-recommendation"
HREF = "/settings/alerts#alert-recommendations"

try:
    from raft.core.observe.alerts.recommendations import AlertRecommendations
except ImportError:  # pragma: no cover - absent until sibling PR merges
    AlertRecommendations = None  # type: ignore[misc, assignment]


class AlertsInboxSource(InboxSource):
    """Surfaces unset alert-setup recommendations when that catalog is installed."""

    def __init__(
        self,
        home: Path,
        *,
        recommendations: Optional[Any] = None,
    ) -> None:
        if recommendations is not None:
            self._recs = recommendations
        elif AlertRecommendations is None:
            raise RuntimeError("alert recommendations package is not installed")
        else:
            self._recs = AlertRecommendations(home)

    @classmethod
    def try_create(
        cls,
        home: Path,
        *,
        recommendations: Optional[Any] = None,
    ) -> Optional["AlertsInboxSource"]:
        """Return a source when the alerts recommendations package exists."""
        if recommendations is not None:
            return cls(home, recommendations=recommendations)
        if AlertRecommendations is None:
            return None
        return cls(home)

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
