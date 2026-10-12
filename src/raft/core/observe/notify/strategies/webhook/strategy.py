"""Webhook NotificationStrategy — HTTP POST JSON to an operator URL."""

import json
import logging
from typing import Any, Mapping, Optional
from urllib.error import URLError

from raft.core.core.errors.cta import OperatorError

from ...delivery_result import DeliveryResult
from ...event import NotificationEvent
from ...strategy import NotificationStrategy
from .gateway import WebhookHttpGateway
from .settings import WebhookSettings

logger = logging.getLogger(__name__)

TYPE_ID = "webhook"


class WebhookStrategy(NotificationStrategy):
    """POST a stable JSON event payload to ``settings.url`` (HTTPS by default)."""

    def __init__(self, *, gateway: Optional[WebhookHttpGateway] = None) -> None:
        self._gateway = gateway or WebhookHttpGateway()
        self._settings = WebhookSettings()

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
        return self._post(event, settings)

    def _post(
        self, event: NotificationEvent, settings: Mapping[str, Any]
    ) -> DeliveryResult:
        body = json.dumps(self._payload(event), separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", **self._settings.headers(settings)}
        url = str(settings["url"]).strip()
        timeout = self._settings.timeout(settings)
        try:
            code = self._gateway.post(url, body, headers, timeout=timeout)
        except URLError:
            return DeliveryResult.failed("URLError: delivery failed")
        except TimeoutError:
            return DeliveryResult.failed("TimeoutError: delivery failed")
        except OSError:
            return DeliveryResult.failed("OSError: delivery failed")
        if 200 <= code < 300:
            return DeliveryResult.success()
        return DeliveryResult.failed(f"HTTP {code}")

    @staticmethod
    def _payload(event: NotificationEvent) -> dict:
        return {
            "kind": event.kind,
            "severity": event.severity.value,
            "title": event.title,
            "body": event.body,
            "context": dict(event.context),
            "timestamp": event.timestamp.isoformat(),
        }

    @staticmethod
    def _safe_operator_error(exc: OperatorError) -> str:
        first = str(exc).split("\n", 1)[0].strip()
        return first or "OperatorError: invalid webhook settings"
