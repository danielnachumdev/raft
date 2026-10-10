"""EmailStrategy validation + deliver with SMTP fakes (no network)."""

from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
import smtplib

from raft.errors.cta import OperatorError
from raft.notify.catalogs import NotificationCatalogs
from raft.notify.strategies.email import TYPE_ID, EmailStrategy
from raft.notify.event import (
    DeliveryStatus,
    NotificationEvent,
    NotificationSeverity,
)
from raft.notify.redact import SettingsRedactor

from tests.unit.base import RaftTestCase


class _FakeSmtp:
    def __init__(self) -> None:
        self.started_tls = False
        self.logins: List[tuple] = []
        self.sent: List[Any] = []

    def __enter__(self) -> "_FakeSmtp":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logins.append((username, password))

    def send_message(self, message: Any) -> None:
        self.sent.append(message)


class TestEmailStrategy(RaftTestCase):
    def test_catalog_registers_email(self) -> None:
        types = [row["type_id"] for row in NotificationCatalogs.default().catalog()]
        assert TYPE_ID in types
        assert "webhook" in types

    def test_validate_requires_addresses_and_host(self) -> None:
        strategy = EmailStrategy()
        with pytest.raises(OperatorError, match="settings.to"):
            strategy.validate_settings({})
        with pytest.raises(OperatorError, match="settings.from"):
            strategy.validate_settings({"to": "ops@example.com"})
        with pytest.raises(OperatorError, match="smtpHost"):
            strategy.validate_settings(
                {"to": "ops@example.com", "from": "raft@example.com"}
            )
        strategy.validate_settings(self._settings())

    def test_validate_port_timeout_auth(self) -> None:
        strategy = EmailStrategy()
        with pytest.raises(OperatorError, match="smtpPort"):
            strategy.validate_settings({**self._settings(), "smtpPort": 0})
        with pytest.raises(OperatorError, match="smtpPort"):
            strategy.validate_settings({**self._settings(), "smtpPort": "x"})
        with pytest.raises(OperatorError, match="timeoutSeconds"):
            strategy.validate_settings({**self._settings(), "timeoutSeconds": 0})
        with pytest.raises(OperatorError, match="timeoutSeconds"):
            strategy.validate_settings({**self._settings(), "timeoutSeconds": "x"})
        with pytest.raises(OperatorError, match="password"):
            strategy.validate_settings({**self._settings(), "username": "u"})
        with pytest.raises(OperatorError, match="password"):
            strategy.validate_settings({**self._settings(), "password": 1})

    def test_deliver_success_plain_text(self) -> None:
        smtp = _FakeSmtp()
        strategy = EmailStrategy(smtp_factory=lambda h, p, t: smtp)
        settings = {
            **self._settings(),
            "username": "raft@example.com",
            "password": "secret",
            "smtpPort": 465,
            "timeoutSeconds": 5,
        }
        result = strategy.deliver(self._event(), settings)
        assert result.status == DeliveryStatus.SUCCESS
        assert smtp.started_tls is True
        assert smtp.logins == [("raft@example.com", "secret")]
        msg = smtp.sent[0]
        assert msg["To"] == "ops@example.com"
        assert msg["Subject"] == "[raft] demo"
        assert "kind: demo.kind" in msg.get_content()

    def test_deliver_skips_tls_and_login_when_unset(self) -> None:
        smtp = _FakeSmtp()
        strategy = EmailStrategy(smtp_factory=lambda h, p, t: smtp)
        event = NotificationEvent(
            kind="demo.kind",
            severity=NotificationSeverity.ERROR,
            title="demo",
            body="demo body",
        )
        result = strategy.deliver(
            event, {**self._settings(), "useStartTls": False}
        )
        assert result.status == DeliveryStatus.SUCCESS
        assert smtp.started_tls is False
        assert smtp.logins == []
        assert "context:" not in smtp.sent[0].get_content()
        smtp2 = _FakeSmtp()
        EmailStrategy(smtp_factory=lambda h, p, t: smtp2).deliver(
            event, {**self._settings(), "useStartTls": "true"}
        )
        assert smtp2.started_tls is True
    def test_deliver_transport_failures(self) -> None:
        strategy = EmailStrategy(smtp_factory=self._raising(smtplib.SMTPException()))
        assert "SMTPException" in strategy.deliver(self._event(), self._settings()).error
        strategy = EmailStrategy(smtp_factory=self._raising(TimeoutError()))
        assert "TimeoutError" in strategy.deliver(self._event(), self._settings()).error
        strategy = EmailStrategy(smtp_factory=self._raising(OSError("down")))
        assert "OSError" in strategy.deliver(self._event(), self._settings()).error

    def test_deliver_invalid_settings_failed_safe(self) -> None:
        result = EmailStrategy(smtp_factory=MagicMock()).deliver(self._event(), {})
        assert result.status == DeliveryStatus.FAILED
        assert "settings.to" in result.error

    def test_password_redacted_for_api(self) -> None:
        redacted = SettingsRedactor().redact(self._settings_with_password())
        assert redacted["password"] == "***"
        assert redacted["to"] == "ops@example.com"

    def test_default_smtp_factory(self) -> None:
        smtp = _FakeSmtp()
        with patch("raft.notify.strategies.email.smtplib.SMTP", return_value=smtp):
            result = EmailStrategy().deliver(self._event(), self._settings())
        assert result.status == DeliveryStatus.SUCCESS
        assert smtp.sent

    @staticmethod
    def _raising(exc: BaseException):
        def factory(host: str, port: int, timeout: float) -> Any:
            raise exc

        return factory

    @staticmethod
    def _settings() -> dict:
        return {
            "to": "ops@example.com",
            "from": "raft@example.com",
            "smtpHost": "smtp.example.com",
        }

    @staticmethod
    def _settings_with_password() -> dict:
        return {
            "to": "ops@example.com",
            "from": "raft@example.com",
            "smtpHost": "smtp.example.com",
            "password": "super-secret",
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
