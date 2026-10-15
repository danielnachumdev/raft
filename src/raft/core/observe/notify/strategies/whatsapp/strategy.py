"""WhatsApp NotificationStrategy — GREEN-API sendMessage text delivery."""

import json
import logging
from typing import Any, Dict, Mapping, Optional
from urllib.error import URLError

from raft.core.core.errors.cta import OperatorError

from ...catalog_field import CatalogField
from ...delivery_result import DeliveryResult
from ...event import NotificationEvent
from ...strategy import NotificationStrategy
from .fields import FIELDS, LABEL
from .gateway import GreenApiHttpGateway
from .settings import WhatsAppSettings

logger = logging.getLogger(__name__)

TYPE_ID = "whatsapp"


class WhatsAppStrategy(NotificationStrategy):
    """POST plain-text alerts via GREEN-API ``sendMessage``."""

    def __init__(self, *, gateway: Optional[GreenApiHttpGateway] = None) -> None:
        self._gateway = gateway or GreenApiHttpGateway()
        self._settings = WhatsAppSettings()

    @property
    def type_id(self) -> str:
        return TYPE_ID

    def catalog_entry(self) -> Dict[str, Any]:
        return CatalogField.entry(TYPE_ID, label=LABEL, fields=FIELDS)

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
        body = json.dumps(self._payload(event, settings), separators=(",", ":"))
        data = body.encode("utf-8")
        headers = {"Content-Type": "application/json"}
        url = self._settings.send_url(settings)
        timeout = self._settings.timeout(settings)
        return self._dispatch(url, data, headers, timeout)

    def _dispatch(
        self, url: str, data: bytes, headers: dict, timeout: float
    ) -> DeliveryResult:
        try:
            code = self._gateway.post(url, data, headers, timeout=timeout)
        except URLError:
            return DeliveryResult.failed("URLError: delivery failed")
        except TimeoutError:
            return DeliveryResult.failed("TimeoutError: delivery failed")
        except OSError:
            return DeliveryResult.failed("OSError: delivery failed")
        logger.info("whatsapp sendMessage HTTP %s", code)
        if 200 <= code < 300:
            return DeliveryResult.success()
        return DeliveryResult.failed(f"HTTP {code}")

    @staticmethod
    def _payload(event: NotificationEvent, settings: Mapping[str, Any]) -> dict:
        return {
            "chatId": str(settings["chatId"]).strip(),
            "message": WhatsAppStrategy._message_text(event),
        }

    @staticmethod
    def _message_text(event: NotificationEvent) -> str:
        lines = [
            f"[raft] {event.title}",
            event.body,
            "",
            f"kind: {event.kind}",
            f"severity: {event.severity.value}",
            f"timestamp: {event.timestamp.isoformat()}",
        ]
        if event.context:
            lines.append("context:")
            for key, value in event.context.items():
                lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _safe_operator_error(exc: OperatorError) -> str:
        first = str(exc).split("\n", 1)[0].strip()
        return first or "OperatorError: invalid whatsapp settings"
