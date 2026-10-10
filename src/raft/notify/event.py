"""Immutable notification event and per-delivery outcome."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class NotificationSeverity(str, Enum):
    """Operator-facing severity for a notification event."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DeliveryStatus(str, Enum):
    """Outcome of one channel delivery attempt."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


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


@dataclass(frozen=True)
class DeliveryResult:
    """Safe per-channel outcome. ``error`` must never carry raw secrets."""

    status: DeliveryStatus
    error: str = ""

    @classmethod
    def success(cls) -> DeliveryResult:
        return cls(DeliveryStatus.SUCCESS)

    @classmethod
    def skipped(cls, reason: str = "") -> DeliveryResult:
        return cls(DeliveryStatus.SKIPPED, error=reason)

    @classmethod
    def failed(cls, error: str) -> DeliveryResult:
        return cls(DeliveryStatus.FAILED, error=error)
