"""Operator-facing severity for a notification event."""

from enum import Enum


class NotificationSeverity(str, Enum):
    """Operator-facing severity for a notification event."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
