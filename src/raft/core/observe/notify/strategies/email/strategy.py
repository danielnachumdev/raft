"""Email NotificationStrategy — plain-text SMTP to an operator address."""

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Mapping, Optional

from raft.core.core.errors.cta import OperatorError

from ...delivery_result import DeliveryResult
from ...event import NotificationEvent
from ...strategy import NotificationStrategy
from .gateway import SmtpGateway
from .settings import EmailSettings

logger = logging.getLogger(__name__)

TYPE_ID = "email"


class EmailStrategy(NotificationStrategy):
    """Send a plain-text message via explicit SMTP settings."""

    def __init__(self, *, gateway: Optional[SmtpGateway] = None) -> None:
        self._gateway = gateway or SmtpGateway()
        self._settings = EmailSettings()

    @property
    def type_id(self) -> str:
        return TYPE_ID

    def validate_settings(self, settings: Mapping[str, Any]) -> None:
        self._settings.validate(settings)

    def deliver(
        self,
        event: NotificationEvent,
        settings: Mapping[str, Any],
    ) -> DeliveryResult:
        try:
            self.validate_settings(settings)
        except OperatorError as exc:
            return DeliveryResult.failed(self._safe_operator_error(exc))
        return self._send(event, settings)

    def _send(
        self, event: NotificationEvent, settings: Mapping[str, Any]
    ) -> DeliveryResult:
        try:
            self._gateway.send(**self._send_kwargs(event, settings))
            return DeliveryResult.success()
        except smtplib.SMTPException:
            return DeliveryResult.failed("SMTPException: delivery failed")
        except TimeoutError:
            return DeliveryResult.failed("TimeoutError: delivery failed")
        except OSError:
            return DeliveryResult.failed("OSError: delivery failed")

    def _send_kwargs(
        self, event: NotificationEvent, settings: Mapping[str, Any]
    ) -> dict:
        return {
            "host": str(settings["smtpHost"]).strip(),
            "port": self._settings.port(settings),
            "timeout": self._settings.timeout(settings),
            "message": self._message(event, settings),
            "username": str(settings.get("username") or "").strip(),
            "password": str(settings.get("password") or ""),
            "start_tls": self._settings.truthy(
                settings.get("useStartTls"), default=True
            ),
        }

    @staticmethod
    def _message(
        event: NotificationEvent, settings: Mapping[str, Any]
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"[raft] {event.title}"
        msg["From"] = str(settings["from"]).strip()
        msg["To"] = str(settings["to"]).strip()
        msg.set_content(EmailStrategy._body_text(event))
        return msg

    @staticmethod
    def _body_text(event: NotificationEvent) -> str:
        body = (
            f"{event.body}\n\n"
            f"kind: {event.kind}\n"
            f"severity: {event.severity.value}\n"
            f"timestamp: {event.timestamp.isoformat()}\n"
        )
        if not event.context:
            return body
        body += "context:\n"
        for key, value in event.context.items():
            body += f"  {key}: {value}\n"
        return body

    @staticmethod
    def _safe_operator_error(exc: OperatorError) -> str:
        first = str(exc).split("\n", 1)[0].strip()
        return first or "OperatorError: invalid email settings"
