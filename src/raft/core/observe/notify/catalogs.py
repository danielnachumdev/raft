"""Shipped notification strategy catalogs (composition root)."""

from .registry import NotificationRegistry
from .strategies.email import EmailStrategy
from .strategies.webhook import WebhookStrategy
from .strategies.whatsapp import WhatsAppStrategy


class NotificationCatalogs:
    """Register concrete strategies for serve catalog + Notifier defaults."""

    @staticmethod
    def default() -> NotificationRegistry:
        registry = NotificationRegistry()
        registry.register(WebhookStrategy())
        registry.register(EmailStrategy())
        registry.register(WhatsAppStrategy())
        return registry
