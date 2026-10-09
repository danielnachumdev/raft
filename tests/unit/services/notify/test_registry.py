"""NotificationRegistry: register, get, catalog, unknown type CTA."""

from __future__ import annotations

import pytest

from raft.errors.cta import OperatorError
from raft.services.notify.registry import NotificationRegistry

from .fakes import FakeStrategy
from ...base import RaftTestCase


class TestNotificationRegistry(RaftTestCase):
    def test_catalog_lists_registered_order(self) -> None:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        registry.register(FakeStrategy("email"))
        assert [row["type_id"] for row in registry.catalog()] == [
            "webhook",
            "email",
        ]

    def test_get_returns_registered_strategy(self) -> None:
        registry = NotificationRegistry()
        strategy = FakeStrategy("webhook")
        registry.register(strategy)
        assert registry.get("webhook") is strategy

    def test_unknown_type_is_operator_error_with_fix(self) -> None:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        with pytest.raises(OperatorError) as caught:
            registry.get("email")
        message = str(caught.value)
        assert "unknown notification type 'email'" in message
        assert "webhook" in message
        assert "Fix:" in message

    def test_unknown_with_empty_catalog(self) -> None:
        registry = NotificationRegistry()
        with pytest.raises(OperatorError, match=r"\(none\)"):
            registry.get("webhook")

    def test_duplicate_register_is_rejected(self) -> None:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        with pytest.raises(ValueError, match="duplicate"):
            registry.register(FakeStrategy("webhook"))
