"""WebhookStrategy validation + deliver with HTTP fakes (no network)."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

import pytest

from raft.errors.cta import OperatorError
from raft.notify.catalogs import NotificationCatalogs
from raft.notify.event import (
    DeliveryStatus,
    NotificationEvent,
    NotificationSeverity,
)
from raft.notify.strategies.webhook import TYPE_ID, WebhookStrategy

from tests.unit.base import RaftTestCase


class _FakeResponse:
    def __init__(self, code: int = 200) -> None:
        self.status = code
        self._buf = BytesIO(b"ok")

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._buf.read()


class TestWebhookStrategy(RaftTestCase):
    def test_catalog_registers_webhook(self) -> None:
        catalog = NotificationCatalogs.default().catalog()
        assert any(item["type_id"] == TYPE_ID for item in catalog)

    def test_validate_requires_https_url(self) -> None:
        strategy = WebhookStrategy()
        with pytest.raises(OperatorError, match="url is required"):
            strategy.validate_settings({})
        with pytest.raises(OperatorError, match="https://"):
            strategy.validate_settings({"url": "http://hooks.example.invalid/x"})
        strategy.validate_settings(
            {"url": "http://127.0.0.1/hook", "allowInsecureHttp": True}
        )
        strategy.validate_settings({"url": "https://hooks.example.invalid/raft"})

    def test_deliver_success_posts_json(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(204))
        strategy = WebhookStrategy(opener=opener)
        settings = {**self._settings(), "timeoutSeconds": 5, "headers": {"X-A": "1"}}
        result = strategy.deliver(self._event(), settings)
        assert result.status == DeliveryStatus.SUCCESS
        req = opener.call_args[0][0]
        assert req.get_method() == "POST"
        assert b'"kind":"demo.kind"' in req.data
        assert opener.call_args[1]["timeout"] == 5.0

    def test_deliver_http_status_failures(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(404))
        strategy = WebhookStrategy(opener=opener)
        assert strategy.deliver(self._event(), self._settings()).error == "HTTP 404"
        opener.side_effect = HTTPError(
            "https://hooks.example.invalid/x", 500, "err", hdrs=None, fp=None
        )
        assert strategy.deliver(self._event(), self._settings()).error == "HTTP 500"

    def test_deliver_transport_failures(self) -> None:
        opener = MagicMock()
        strategy = WebhookStrategy(opener=opener)
        opener.side_effect = URLError("down")
        assert "URLError" in strategy.deliver(self._event(), self._settings()).error
        opener.side_effect = TimeoutError()
        assert "TimeoutError" in strategy.deliver(self._event(), self._settings()).error
        opener.side_effect = OSError("broken")
        assert "OSError" in strategy.deliver(self._event(), self._settings()).error

    def test_deliver_invalid_settings_failed_safe(self) -> None:
        result = WebhookStrategy(opener=MagicMock()).deliver(self._event(), {})
        assert result.status == DeliveryStatus.FAILED
        assert "url is required" in result.error

    def test_timeout_validation(self) -> None:
        strategy = WebhookStrategy()
        with pytest.raises(OperatorError, match="timeoutSeconds"):
            strategy.validate_settings(
                {"url": "https://hooks.example.invalid/x", "timeoutSeconds": 0}
            )
        with pytest.raises(OperatorError, match="timeoutSeconds"):
            strategy.validate_settings(
                {"url": "https://hooks.example.invalid/x", "timeoutSeconds": "x"}
            )

    def test_headers_validation(self) -> None:
        strategy = WebhookStrategy()
        with pytest.raises(OperatorError, match="headers"):
            strategy.validate_settings(
                {"url": "https://hooks.example.invalid/x", "headers": "nope"}
            )
        with pytest.raises(OperatorError, match="headers"):
            strategy.validate_settings(
                {"url": "https://hooks.example.invalid/x", "headers": {"X-A": 1}}
            )
        strategy.validate_settings(
            {
                "url": "https://hooks.example.invalid/x",
                "timeoutSeconds": 10,
                "headers": {"Authorization": "Bearer x"},
            }
        )

    @staticmethod
    def _settings() -> dict:
        return {"url": "https://hooks.example.invalid/raft"}

    @staticmethod
    def _event() -> NotificationEvent:
        return NotificationEvent(
            kind="demo.kind",
            severity=NotificationSeverity.ERROR,
            title="demo",
            body="demo body",
            context={"app": "demo-api"},
        )
