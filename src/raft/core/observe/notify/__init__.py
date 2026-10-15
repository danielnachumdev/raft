"""In-process notification dispatch (strategy ABC, registry, dispatcher)."""

from .catalogs import NotificationCatalogs
from .channel import ChannelDescriptor
from .channel_delivery import ChannelDelivery
from .control_events import ControlPlaneEvents
from .delivery_result import DeliveryResult
from .delivery_status import DeliveryStatus
from .dispatcher import NotificationDispatcher
from .event import NotificationEvent
from .notifier import Notifier
from .registry import NotificationRegistry
from .settings_redactor import SettingsRedactor
from .severity import NotificationSeverity
from .strategies import EmailStrategy, WebhookStrategy, WhatsAppStrategy
from .strategy import NotificationStrategy

__all__ = [
    "ChannelDelivery",
    "ChannelDescriptor",
    "ControlPlaneEvents",
    "DeliveryResult",
    "DeliveryStatus",
    "EmailStrategy",
    "NotificationCatalogs",
    "NotificationDispatcher",
    "NotificationEvent",
    "NotificationRegistry",
    "NotificationSeverity",
    "NotificationStrategy",
    "Notifier",
    "SettingsRedactor",
    "WebhookStrategy",
    "WhatsAppStrategy",
]
