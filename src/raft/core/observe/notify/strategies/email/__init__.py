"""Email NotificationStrategy + SMTP gateway."""

from .gateway import SmtpGateway
from .strategy import TYPE_ID, EmailStrategy

__all__ = ["EmailStrategy", "SmtpGateway", "TYPE_ID"]
