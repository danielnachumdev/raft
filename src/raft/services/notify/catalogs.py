"""Shipped notification strategy catalogs (composition root)."""

from __future__ import annotations

from .email import EmailStrategy
from .registry import NotificationRegistry
from .webhook import WebhookStrategy


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
