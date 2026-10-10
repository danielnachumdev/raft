"""NotificationEvent and DeliveryResult contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from raft.notify.event import (
    DeliveryResult,
    DeliveryStatus,
    NotificationEvent,
    NotificationSeverity,
)

from tests.unit.base import RaftTestCase


class TestNotificationEvent(RaftTestCase):
    def test_context_is_immutable(self) -> None:
        event = NotificationEvent(
            kind="demo.heal",
            severity=NotificationSeverity.WARNING,
            title="demo-app unhealthy",
            body="healer skipped scaledToZero",
            context={"app": "demo-app", "token": "not-a-real-secret"},
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        with pytest.raises(TypeError):
            event.context["app"] = "other"  # type: ignore[index]
        assert event.kind == "demo.heal"
        assert event.severity is NotificationSeverity.WARNING

    def test_default_context_and_timestamp(self) -> None:
        event = NotificationEvent(
            kind="demo.info",
            severity=NotificationSeverity.INFO,
            title="t",
            body="b",
        )
        assert dict(event.context) == {}
        assert event.timestamp.tzinfo is not None


class TestDeliveryResult(RaftTestCase):
    def test_helpers(self) -> None:
        assert DeliveryResult.success().status is DeliveryStatus.SUCCESS
        skipped = DeliveryResult.skipped("channel disabled")
        assert skipped.status is DeliveryStatus.SKIPPED
        assert skipped.error == "channel disabled"
        failed = DeliveryResult.failed("smtp unavailable")
        assert failed.status is DeliveryStatus.FAILED
        assert failed.error == "smtp unavailable"
