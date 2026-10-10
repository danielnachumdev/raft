"""Webhook NotificationStrategy — HTTP POST JSON to an operator URL."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from raft.errors.cta import OperatorError

from ..event import DeliveryResult, NotificationEvent
from ..strategy import NotificationStrategy

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0
TYPE_ID = "webhook"


class WebhookStrategy(NotificationStrategy):
    """POST a stable JSON event payload to ``settings.url`` (HTTPS by default)."""

    def __init__(self, *, opener: Optional[Any] = None) -> None:
        self._opener = opener or urlopen

    @property
    def type_id(self) -> str:
        return TYPE_ID

    def validate_settings(self, settings: Mapping[str, Any]) -> None:
        url = self._require_url(settings)
        self._assert_https(url, settings)
        self._assert_timeout(settings)
        self._assert_headers(settings)

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
        request = self._request(event, settings)
        timeout = self._timeout(settings)
        try:
            with self._opener(request, timeout=timeout) as response:
                code = getattr(response, "status", None) or response.getcode()
                if 200 <= int(code) < 300:
                    return DeliveryResult.success()
                return DeliveryResult.failed(f"HTTP {code}")
        except HTTPError as exc:
            return DeliveryResult.failed(f"HTTP {exc.code}")
        except URLError:
            return DeliveryResult.failed("URLError: delivery failed")
        except TimeoutError:
            return DeliveryResult.failed("TimeoutError: delivery failed")
        except OSError:
            return DeliveryResult.failed("OSError: delivery failed")

    def _request(
        self, event: NotificationEvent, settings: Mapping[str, Any]
    ) -> Request:
        body = json.dumps(self._payload(event), separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", **self._headers(settings)}
        return Request(
            str(settings["url"]).strip(),
            data=body,
            headers=headers,
            method="POST",
        )

    @staticmethod
    def _payload(event: NotificationEvent) -> dict[str, Any]:
        return {
            "kind": event.kind,
            "severity": event.severity.value,
            "title": event.title,
            "body": event.body,
            "context": dict(event.context),
            "timestamp": event.timestamp.isoformat(),
        }

    @staticmethod
    def _require_url(settings: Mapping[str, Any]) -> str:
        url = str(settings.get("url") or "").strip()
        if not url:
            raise OperatorError(
                "webhook settings.url is required.\n"
                "Fix: set settings.url to an https://hooks.example.invalid/… URL",
                has_fix=False,
            )
        return url

    @staticmethod
    def _assert_https(url: str, settings: Mapping[str, Any]) -> None:
        if url.lower().startswith("https://"):
            return
        if url.lower().startswith("http://") and bool(settings.get("allowInsecureHttp")):
            return
        raise OperatorError(
            "webhook settings.url must use https:// "
            "(or set allowInsecureHttp: true for lab http:// only).\n"
            "Fix: use https://hooks.example.invalid/raft",
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
                "webhook settings.timeoutSeconds must be a number.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            ) from exc
        if value <= 0:
            raise OperatorError(
                "webhook settings.timeoutSeconds must be > 0.\n"
                "Fix: set timeoutSeconds: 10",
                has_fix=False,
            )

    @staticmethod
    def _assert_headers(settings: Mapping[str, Any]) -> None:
        headers = settings.get("headers")
        if headers is None:
            return
        if not isinstance(headers, Mapping):
            raise OperatorError(
                "webhook settings.headers must be a mapping of string to string.\n"
                "Fix: set headers: {Authorization: Bearer …}",
                has_fix=False,
            )
        for key, value in headers.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise OperatorError(
                    "webhook settings.headers values must be strings.\n"
                    "Fix: use string header names and values only",
                    has_fix=False,
                )

    @staticmethod
    def _timeout(settings: Mapping[str, Any]) -> float:
        raw = settings.get("timeoutSeconds")
        if raw is None:
            return DEFAULT_TIMEOUT_SECONDS
        return float(raw)

    @staticmethod
    def _headers(settings: Mapping[str, Any]) -> dict[str, str]:
        headers = settings.get("headers") or {}
        return {str(k): str(v) for k, v in dict(headers).items()}

    @staticmethod
    def _safe_operator_error(exc: OperatorError) -> str:
        first = str(exc).split("\n", 1)[0].strip()
        return first or "OperatorError: invalid webhook settings"
