"""Concrete NotificationStrategy implementations."""

from .email import EmailStrategy
from .webhook import WebhookStrategy

__all__ = ["EmailStrategy", "WebhookStrategy"]
