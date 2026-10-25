"""Aggregate operator-inbox items and persist read/unread state."""

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.inbox.badge import InboxBadge
from raft.core.observe.inbox.item import InboxItem, parse_inbox_item_id
from raft.core.observe.inbox.read_store import InboxReadStore
from raft.core.observe.inbox.sources.base import InboxSource
from raft.core.observe.inbox.sources.registry import InboxSourceRegistry
from raft.core.platform.locking import InboxLock


class OperatorInboxService:
    """Derived multi-source inbox with durable read markers under host/inbox/."""

    def __init__(
        self,
        home: Path,
        *,
        sources: Optional[Sequence[InboxSource]] = None,
        read_store: Optional[InboxReadStore] = None,
    ) -> None:
        self._home = home
        self._sources = list(sources or InboxSourceRegistry.default(home))
        self._read = read_store or InboxReadStore(home)
        self._by_source = {source.source_id: source for source in self._sources}

    def list_public(self) -> Dict[str, Any]:
        items = self._annotated_items()
        unread = sum(1 for item in items if item.unread)
        return {
            "items": [item.to_public() for item in items],
            "unreadCount": unread,
            "badge": InboxBadge.format(unread),
            "badgeSemantics": "unread",
        }

    def summary(self) -> Dict[str, Any]:
        items = self._annotated_items()
        unread = sum(1 for item in items if item.unread)
        return {
            "unreadCount": unread,
            "badge": InboxBadge.format(unread),
            "badgeSemantics": "unread",
            "totalCount": len(items),
        }

    def mark_read(self, item_ids: Iterable[str]) -> Dict[str, Any]:
        with InboxLock(self._home):
            self._read.mark_read(item_ids)
            self._prune_locked()
        return self.list_public()

    def mark_unread(self, item_ids: Iterable[str]) -> Dict[str, Any]:
        with InboxLock(self._home):
            self._read.mark_unread(item_ids)
            self._prune_locked()
        return self.list_public()

    def mark_all_read(self) -> Dict[str, Any]:
        items = self._raw_items()
        with InboxLock(self._home):
            self._read.mark_read(item.id for item in items)
            self._prune_locked(live_ids={item.id for item in items})
        return self.list_public()

    def dismiss(self, item_id: str) -> Dict[str, Any]:
        source_id, source_item_id = self._require_parts(item_id)
        source = self._require_source(source_id)
        self._dismiss_on_source(source, source_id, source_item_id)
        with InboxLock(self._home):
            self._read.mark_unread([item_id])
            self._prune_locked()
        return self.list_public()

    def _annotated_items(self) -> List[InboxItem]:
        read_ids = self._read.list_read_ids()
        return [
            item.with_unread(item.id not in read_ids) for item in self._raw_items()
        ]

    def _raw_items(self) -> List[InboxItem]:
        items: List[InboxItem] = []
        for source in self._sources:
            items.extend(source.list_items())
        return items

    def _prune_locked(self, *, live_ids: Optional[set] = None) -> None:
        ids = live_ids if live_ids is not None else {item.id for item in self._raw_items()}
        self._read.prune_to(ids)

    def _require_source(self, source_id: str) -> InboxSource:
        source = self._by_source.get(source_id)
        if source is None:
            raise OperatorError(
                f"Unknown inbox source {source_id!r}.\n"
                "Fix: refresh the inbox and try again"
            )
        return source

    @staticmethod
    def _dismiss_on_source(
        source: InboxSource, source_id: str, source_item_id: str
    ) -> None:
        try:
            source.dismiss(source_item_id)
        except NotImplementedError as exc:
            raise OperatorError(
                f"Inbox source {source_id!r} does not support dismiss.\n"
                "Fix: open the linked page to manage this item"
            ) from exc

    @staticmethod
    def _require_parts(item_id: str) -> Tuple[str, str]:
        parts = parse_inbox_item_id(item_id)
        if parts is None:
            raise OperatorError(
                f"Malformed inbox item id {item_id!r}.\n"
                "Fix: refresh the inbox and try again"
            )
        return parts
