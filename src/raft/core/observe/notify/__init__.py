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
from .settings_write import NotificationsSettingsWriter
from .severity import NotificationSeverity
from .strategies import EmailStrategy, WebhookStrategy, WhatsAppStrategy
from .strategy import NotificationStrategy
from .tester import KIND_NOTIFICATIONS_TEST, NotificationsTester

__all__ = [
    "ChannelDelivery",
    "ChannelDescriptor",
    "ControlPlaneEvents",
    "DeliveryResult",
    "DeliveryStatus",
    "EmailStrategy",
    "KIND_NOTIFICATIONS_TEST",
    "NotificationCatalogs",
    "NotificationDispatcher",
    "NotificationEvent",
    "NotificationRegistry",
    "NotificationSeverity",
    "NotificationStrategy",
    "NotificationsSettingsWriter",
    "NotificationsTester",
    "Notifier",
    "SettingsRedactor",
    "WebhookStrategy",
    "WhatsAppStrategy",
]
