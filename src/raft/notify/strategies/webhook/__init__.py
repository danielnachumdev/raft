"""Webhook NotificationStrategy + HTTP gateway."""

from .gateway import WebhookHttpGateway
from .strategy import TYPE_ID, WebhookStrategy

__all__ = ["TYPE_ID", "WebhookHttpGateway", "WebhookStrategy"]
