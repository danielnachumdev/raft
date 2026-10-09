"""NotificationDispatcher: fan-out, skip disabled, isolate failures."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from raft.errors.cta import OperatorError
from raft.services.notify.channel import ChannelDescriptor
from raft.services.notify.dispatcher import NotificationDispatcher
from raft.services.notify.event import (
    DeliveryResult,
    DeliveryStatus,
    NotificationEvent,
    NotificationSeverity,
)
from raft.services.notify.registry import NotificationRegistry

from .fakes import FakeStrategy
from ...base import RaftTestCase


def _event() -> NotificationEvent:
    return NotificationEvent(
        kind="demo.scale",
        severity=NotificationSeverity.ERROR,
        title="demo-app wake timeout",
        body="wake exceeded budget",
        context={"app": "demo-app", "id": "diag-demo-001"},
        timestamp=datetime(2026, 3, 4, tzinfo=timezone.utc),
    )


def _registry(*strategies: FakeStrategy) -> NotificationRegistry:
    registry = NotificationRegistry()
    for strategy in strategies:
        registry.register(strategy)
    return registry


class TestNotificationDispatcher(RaftTestCase):
    def test_fan_out_to_enabled_channels(self) -> None:
        webhook, email = FakeStrategy("webhook"), FakeStrategy("email")
        dispatcher = NotificationDispatcher(_registry(webhook, email))
        results = dispatcher.dispatch(
            _event(),
            [
                ChannelDescriptor("wh-1", "webhook"),
                ChannelDescriptor("em-1", "email"),
            ],
        )
        assert [row.channel_id for row in results] == ["wh-1", "em-1"]
        assert all(row.result.status is DeliveryStatus.SUCCESS for row in results)
        assert len(webhook.delivered) == len(email.delivered) == 1

    def test_disabled_channel_is_skipped(self) -> None:
        webhook = FakeStrategy("webhook")
        results = NotificationDispatcher(_registry(webhook)).dispatch(
            _event(),
            [
                ChannelDescriptor("wh-off", "webhook", enabled=False),
                ChannelDescriptor("wh-on", "webhook", enabled=True),
            ],
        )
        assert results[0].result.status is DeliveryStatus.SKIPPED
        assert results[0].result.error == "channel disabled"
        assert results[1].result.status is DeliveryStatus.SUCCESS
        assert len(webhook.delivered) == 1

    def test_unknown_type_raises_operator_error(self) -> None:
        dispatcher = NotificationDispatcher(_registry(FakeStrategy("webhook")))
        with pytest.raises(OperatorError) as caught:
            dispatcher.dispatch(_event(), [ChannelDescriptor("bad", "email")])
        assert "Fix:" in str(caught.value)

    def test_one_failing_channel_does_not_block_others(self) -> None:
        boom = FakeStrategy(
            "webhook",
            raise_on_deliver=RuntimeError("smtp://user:hunter2@demo-host"),
        )
        ok = FakeStrategy("email")
        results = NotificationDispatcher(_registry(boom, ok)).dispatch(
            _event(),
            [
                ChannelDescriptor("wh-1", "webhook", settings={"secret": "hunter2"}),
                ChannelDescriptor("em-1", "email"),
            ],
        )
        assert results[0].result.status is DeliveryStatus.FAILED
        assert results[1].result.status is DeliveryStatus.SUCCESS
        assert "hunter2" not in results[0].result.error
        assert "RuntimeError" in results[0].result.error
        assert len(ok.delivered) == 1

    def test_validate_settings_failure_is_isolated(self) -> None:
        bad, ok = FakeStrategy("webhook", reject_settings=True), FakeStrategy("email")
        results = NotificationDispatcher(_registry(bad, ok)).dispatch(
            _event(),
            [ChannelDescriptor("wh-1", "webhook"), ChannelDescriptor("em-1", "email")],
        )
        assert results[0].result.status is DeliveryStatus.FAILED
        assert results[1].result.status is DeliveryStatus.SUCCESS
        assert "OperatorError" in results[0].result.error

    def test_soft_failed_result_passes_through(self) -> None:
        soft = FakeStrategy("webhook", result=DeliveryResult.failed("upstream 503"))
        results = NotificationDispatcher(_registry(soft)).dispatch(
            _event(),
            [ChannelDescriptor("wh-1", "webhook")],
        )
        assert results[0].result.error == "upstream 503"

    def test_channel_settings_are_immutable(self) -> None:
        channel = ChannelDescriptor(
            "wh-1",
            "webhook",
            settings={"url": "https://example.com/hook"},
        )
        with pytest.raises(TypeError):
            channel.settings["url"] = "https://evil.example"  # type: ignore[index]
