"""Normalized operator-inbox feed item (derived from heterogeneous sources)."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class InboxItem:
    """One attention item with stable id and optional deep-link href."""

    id: str
    source: str
    source_item_id: str
    title: str
    summary: str
    severity: str
    href: str
    dismissible: bool
    unread: bool = True

    def to_public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "sourceItemId": self.source_item_id,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity,
            "href": self.href,
            "dismissible": self.dismissible,
            "unread": self.unread,
        }

    def with_unread(self, unread: bool) -> "InboxItem":
        return InboxItem(
            id=self.id,
            source=self.source,
            source_item_id=self.source_item_id,
            title=self.title,
            summary=self.summary,
            severity=self.severity,
            href=self.href,
            dismissible=self.dismissible,
            unread=unread,
        )


def inbox_item_id(source: str, source_item_id: str) -> str:
    """Stable feed id: ``{source}:{source_item_id}``."""
    return f"{source}:{source_item_id}"


def parse_inbox_item_id(item_id: str) -> Optional[tuple[str, str]]:
    """Split ``source:source_item_id``; None when malformed."""
    text = item_id.strip()
    if ":" not in text:
        return None
    source, _, rest = text.partition(":")
    if not source or not rest:
        return None
    return source, rest
