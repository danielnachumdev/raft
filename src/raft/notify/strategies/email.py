"""Email NotificationStrategy — plain-text SMTP to an operator address."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Callable, Mapping, Optional

from raft.errors.cta import OperatorError

from ..event import DeliveryResult, NotificationEvent
from ..strategy import NotificationStrategy

logger = logging.getLogger(__name__)

TYPE_ID = "email"
DEFAULT_PORT = 587
DEFAULT_TIMEOUT_SECONDS = 10.0
SmtpFactory = Callable[[str, int, float], Any]


class EmailStrategy(NotificationStrategy):
    """Send a plain-text message via explicit SMTP settings."""

    def __init__(self, *, smtp_factory: Optional[SmtpFactory] = None) -> None:
        self._smtp_factory = smtp_factory or self._default_smtp

    @property
    def type_id(self) -> str:
        return TYPE_ID

    def validate_settings(self, settings: Mapping[str, Any]) -> None:
        self._require_address(settings, "to")
        self._require_address(settings, "from")
        self._require_host(settings)
        self._assert_port(settings)
        self._assert_timeout(settings)
        self._assert_auth(settings)

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
        message = self._message(event, settings)
        host = str(settings["smtpHost"]).strip()
        port = self._port(settings)
        timeout = self._timeout(settings)
        try:
            with self._smtp_factory(host, port, timeout) as smtp:
                self._authenticate(smtp, settings)
                smtp.send_message(message)
            return DeliveryResult.success()
        except smtplib.SMTPException:
            return DeliveryResult.failed("SMTPException: delivery failed")
        except TimeoutError:
            return DeliveryResult.failed("TimeoutError: delivery failed")
        except OSError:
            return DeliveryResult.failed("OSError: delivery failed")

    def _authenticate(self, smtp: Any, settings: Mapping[str, Any]) -> None:
        if self._truthy(settings.get("useStartTls"), default=True):
            smtp.starttls()
        username = str(settings.get("username") or "").strip()
        if not username:
            return
        password = str(settings.get("password") or "")
        smtp.login(username, password)

    @staticmethod
    def _message(
        event: NotificationEvent, settings: Mapping[str, Any]
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"[raft] {event.title}"
        msg["From"] = str(settings["from"]).strip()
        msg["To"] = str(settings["to"]).strip()
        body = (
            f"{event.body}\n\n"
            f"kind: {event.kind}\n"
            f"severity: {event.severity.value}\n"
            f"timestamp: {event.timestamp.isoformat()}\n"
        )
        if event.context:
            body += "context:\n"
            for key, value in event.context.items():
                body += f"  {key}: {value}\n"
        msg.set_content(body)
        return msg

    @staticmethod
    def _require_address(settings: Mapping[str, Any], key: str) -> str:
        value = str(settings.get(key) or "").strip()
        if not value or "@" not in value:
            raise OperatorError(
                f"email settings.{key} must be an address "
                f"(e.g. ops@example.com).\n"
                f"Fix: set settings.{key}: ops@example.com",
                has_fix=False,
            )
        return value

    @staticmethod
    def _require_host(settings: Mapping[str, Any]) -> str:
        host = str(settings.get("smtpHost") or "").strip()
        if not host:
            raise OperatorError(
                "email settings.smtpHost is required.\n"
                "Fix: set smtpHost: smtp.example.com",
                has_fix=False,
            )
        return host

    @staticmethod
    def _assert_port(settings: Mapping[str, Any]) -> None:
        if "smtpPort" not in settings or settings["smtpPort"] is None:
            return
        try:
            port = int(settings["smtpPort"])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                "email settings.smtpPort must be an integer.\n"
                "Fix: set smtpPort: 587",
                has_fix=False,
            ) from exc
        if not 1 <= port <= 65535:
            raise OperatorError(
                "email settings.smtpPort must be 1–65535.\n"
                "Fix: set smtpPort: 587",
                has_fix=False,
            )

    @staticmethod
    def _assert_timeout(settings: Mapping[str, Any]) -> None:
        if "timeoutSeconds" not in settings or settings["timeoutSeconds"] is None:
            return
        try:
            value = float(settings["timeoutSeconds"])
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                "email settings.timeoutSeconds must be a number.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            ) from exc
        if value <= 0:
            raise OperatorError(
                "email settings.timeoutSeconds must be > 0.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            )

    @staticmethod
    def _assert_auth(settings: Mapping[str, Any]) -> None:
        username = str(settings.get("username") or "").strip()
        password = settings.get("password")
        if username and password is None:
            raise OperatorError(
                "email settings.password is required when username is set.\n"
                "Fix: set password (redacted in serve API)",
                has_fix=False,
            )
        if password is not None and not isinstance(password, str):
            raise OperatorError(
                "email settings.password must be a string.\n"
                "Fix: set password as a string value",
                has_fix=False,
            )

    @staticmethod
    def _port(settings: Mapping[str, Any]) -> int:
        raw = settings.get("smtpPort")
        return DEFAULT_PORT if raw is None else int(raw)

    @staticmethod
    def _timeout(settings: Mapping[str, Any]) -> float:
        raw = settings.get("timeoutSeconds")
        return DEFAULT_TIMEOUT_SECONDS if raw is None else float(raw)

    @staticmethod
    def _truthy(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _default_smtp(host: str, port: int, timeout: float) -> Any:
        return smtplib.SMTP(host, port, timeout=timeout)

    @staticmethod
    def _safe_operator_error(exc: OperatorError) -> str:
        first = str(exc).split("\n", 1)[0].strip()
        return first or "OperatorError: invalid email settings"
