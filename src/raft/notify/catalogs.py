"""Shipped notification strategy catalogs (composition root)."""

from __future__ import annotations

from .registry import NotificationRegistry
from .strategies.email import EmailStrategy
from .strategies.webhook import WebhookStrategy


class NotificationCatalogs:
    """Register concrete strategies for serve catalog + Notifier defaults.

    Add WhatsApp later with ``registry.register(…)`` here — do not change
    the dispatcher or SPA shell.
    """

    @staticmethod
    def default() -> NotificationRegistry:
        registry = NotificationRegistry()
        registry.register(WebhookStrategy())
        registry.register(EmailStrategy())
        return registry
