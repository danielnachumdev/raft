"""WhatsAppStrategy validation + deliver with HTTP fakes (no network)."""

from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.notify.catalogs import NotificationCatalogs
from raft.core.observe.notify.delivery_status import DeliveryStatus
from raft.core.observe.notify.event import NotificationEvent
from raft.core.observe.notify.severity import NotificationSeverity
from raft.core.observe.notify.settings_redactor import SettingsRedactor
from raft.core.observe.notify.strategies.whatsapp import (
    TYPE_ID,
    GreenApiHttpGateway,
    WhatsAppStrategy,
)

from tests.unit.base import RaftTestCase


class _FakeResponse:
    def __init__(self, code: int = 200) -> None:
        self.status = code
        self._buf = BytesIO(b'{"idMessage":"demo"}')

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self._buf.read()


class TestWhatsAppStrategy(RaftTestCase):
    def test_catalog_registers_whatsapp(self) -> None:
        entry = next(
            row
            for row in NotificationCatalogs.default().catalog()
            if row["type_id"] == TYPE_ID
        )
        assert entry["label"] == "WhatsApp (GREEN-API)"
        keys = [field["key"] for field in entry["fields"]]
        assert keys[:4] == ["apiUrl", "idInstance", "apiTokenInstance", "chatId"]

    def test_validate_requires_core_fields(self) -> None:
        strategy = WhatsAppStrategy()
        with pytest.raises(OperatorError, match="apiUrl is required"):
            strategy.validate_settings({})
        with pytest.raises(OperatorError, match="https://"):
            strategy.validate_settings({"apiUrl": "http://api.example.invalid"})
        with pytest.raises(OperatorError, match="idInstance"):
            strategy.validate_settings({"apiUrl": "https://api.green-api.com"})
        strategy.validate_settings(self._settings())

    def test_validate_token_chat_timeout(self) -> None:
        strategy = WhatsAppStrategy()
        base = {"apiUrl": "https://api.green-api.com", "idInstance": 1101}
        with pytest.raises(OperatorError, match="apiTokenInstance"):
            strategy.validate_settings({**base, "chatId": "79001234567@c.us"})
        with pytest.raises(OperatorError, match="apiTokenInstance must be"):
            strategy.validate_settings(
                {**base, "apiTokenInstance": 1, "chatId": "79001234567@c.us"}
            )
        with pytest.raises(OperatorError, match="chatId"):
            strategy.validate_settings({**base, "apiTokenInstance": "tok"})
        with pytest.raises(OperatorError, match="timeoutSeconds"):
            strategy.validate_settings({**self._settings(), "timeoutSeconds": 0})
        with pytest.raises(OperatorError, match="timeoutSeconds"):
            strategy.validate_settings({**self._settings(), "timeoutSeconds": "x"})

    def test_deliver_success_posts_send_message(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(200))
        strategy = WhatsAppStrategy(gateway=GreenApiHttpGateway(opener=opener))
        settings = {**self._settings(), "timeoutSeconds": 5, "idInstance": 1101000001}
        result = strategy.deliver(self._event(), settings)
        assert result.status == DeliveryStatus.SUCCESS
        req = opener.call_args[0][0]
        assert req.get_method() == "POST"
        assert "/waInstance1101000001/sendMessage/" in req.full_url
        assert "demo-token-not-real" in req.full_url
        assert b'"chatId":"79001234567@c.us"' in req.data
        assert b"[raft] demo" in req.data
        assert opener.call_args[1]["timeout"] == 5.0

    def test_deliver_http_and_transport_failures(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(404))
        strategy = WhatsAppStrategy(gateway=GreenApiHttpGateway(opener=opener))
        assert strategy.deliver(self._event(), self._settings()).error == "HTTP 404"
        opener.side_effect = HTTPError(
            "https://api.green-api.com/x", 500, "err", hdrs=None, fp=None
        )
        assert strategy.deliver(self._event(), self._settings()).error == "HTTP 500"
        opener.side_effect = URLError("down")
        assert "URLError" in strategy.deliver(self._event(), self._settings()).error
        opener.side_effect = TimeoutError()
        assert "TimeoutError" in strategy.deliver(self._event(), self._settings()).error
        opener.side_effect = OSError("broken")
        assert "OSError" in strategy.deliver(self._event(), self._settings()).error

    def test_deliver_invalid_settings_failed_safe(self) -> None:
        result = WhatsAppStrategy(
            gateway=GreenApiHttpGateway(opener=MagicMock())
        ).deliver(self._event(), {})
        assert result.status == DeliveryStatus.FAILED
        assert "apiUrl is required" in result.error

    def test_token_redacted_and_merge_preserves(self) -> None:
        redactor = SettingsRedactor()
        redacted = redactor.redact(self._settings())
        assert redacted["apiTokenInstance"] == "***"
        assert redacted["chatId"] == "79001234567@c.us"
        merged = redactor.merge_preserving_secrets(
            self._settings(),
            {**self._settings(), "apiTokenInstance": "***", "chatId": "1@c.us"},
        )
        assert merged["apiTokenInstance"] == "demo-token-not-real"
        assert merged["chatId"] == "1@c.us"

    def test_logs_status_not_token(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(200))
        strategy = WhatsAppStrategy(gateway=GreenApiHttpGateway(opener=opener))
        with patch(
            "raft.core.observe.notify.strategies.whatsapp.strategy.logger"
        ) as log:
            strategy.deliver(self._event(), self._settings())
        args = log.info.call_args[0]
        assert args[0] == "whatsapp sendMessage HTTP %s"
        assert args[1] == 200
        assert "demo-token-not-real" not in str(args)

    def test_message_includes_context(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(200))
        strategy = WhatsAppStrategy(gateway=GreenApiHttpGateway(opener=opener))
        strategy.deliver(self._event(), self._settings())
        assert b"app: demo-api" in opener.call_args[0][0].data

    def test_message_without_context(self) -> None:
        opener = MagicMock(return_value=_FakeResponse(200))
        strategy = WhatsAppStrategy(gateway=GreenApiHttpGateway(opener=opener))
        event = NotificationEvent(
            kind="demo.kind",
            severity=NotificationSeverity.INFO,
            title="demo",
            body="demo body",
        )
        strategy.deliver(event, self._settings())
        assert b"context:" not in opener.call_args[0][0].data

    @staticmethod
    def _settings() -> dict:
        return {
            "apiUrl": "https://api.green-api.com",
            "idInstance": "1101000001",
            "apiTokenInstance": "demo-token-not-real",
            "chatId": "79001234567@c.us",
        }

    @staticmethod
    def _event() -> NotificationEvent:
        return NotificationEvent(
            kind="demo.kind",
            severity=NotificationSeverity.ERROR,
            title="demo",
            body="demo body",
            context={"app": "demo-api"},
        )
