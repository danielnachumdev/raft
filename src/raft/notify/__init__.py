"""In-process notification dispatch (strategy ABC, registry, dispatcher)."""

from .catalogs import NotificationCatalogs
from .channel import ChannelDescriptor
from .control_events import ControlPlaneEvents
from .dispatcher import NotificationDispatcher
from .event import DeliveryResult, NotificationEvent, NotificationSeverity
from .notifier import Notifier
from .registry import NotificationRegistry
from .strategies import EmailStrategy, WebhookStrategy
from .strategy import NotificationStrategy

__all__ = [
    "ChannelDescriptor",
    "ControlPlaneEvents",
    "DeliveryResult",
    "EmailStrategy",
    "NotificationCatalogs",
    "NotificationDispatcher",
    "NotificationEvent",
    "NotificationRegistry",
    "NotificationSeverity",
    "NotificationStrategy",
    "Notifier",
    "WebhookStrategy",
]
