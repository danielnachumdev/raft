"""Immutable notification event."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .severity import NotificationSeverity


@dataclass(frozen=True)
class NotificationEvent:
    """One outbound alert. ``context`` is opaque to the framework."""

    kind: str
    severity: NotificationSeverity
    title: str
    body: str
    context: Mapping[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", MappingProxyType(dict(self.context)))
