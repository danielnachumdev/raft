"""NotificationsTester: probe event through one channel."""

from __future__ import annotations

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.notify.delivery_result import DeliveryResult
from raft.core.observe.notify.delivery_status import DeliveryStatus
from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_write import NotificationsSettingsWriter
from raft.core.observe.notify.tester import (
    KIND_NOTIFICATIONS_TEST,
    NotificationsTester,
)

from tests.unit.base import RaftTestCase
from tests.unit.core.observe.notify.fakes import FakeStrategy


class TestNotificationsTester(RaftTestCase):
    def _registry(self) -> NotificationRegistry:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        return registry

    def test_send_delivers_probe_even_when_disabled(self) -> None:
        registry = self._registry()
        fake = FakeStrategy("webhook")
        registry = NotificationRegistry()
        registry.register(fake)
        writer = NotificationsSettingsWriter(self.tmp_path, registry=registry)
        writer.create(
            {
                "id": "ops-webhook",
                "type": "webhook",
                "enabled": False,
                "settings": {"url": "https://example.invalid/hooks/demo-api"},
            }
        )
        deliveries = NotificationsTester(
            self.tmp_path, registry=registry
        ).send("ops-webhook")
        assert len(deliveries) == 1
        assert deliveries[0].result.status == DeliveryStatus.SUCCESS
        assert fake.delivered[0].kind == KIND_NOTIFICATIONS_TEST
        assert fake.delivered[0].context["channel_id"] == "ops-webhook"

    def test_missing_channel_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            NotificationsTester(
                self.tmp_path, registry=self._registry()
            ).send("missing")

    def test_unknown_type_raises_operator_error(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(
            {
                "id": "ops",
                "type": "webhook",
                "settings": {"url": "https://example.invalid/hooks/demo-api"},
            }
        )
        empty = NotificationRegistry()
        with pytest.raises(OperatorError, match="ops"):
            NotificationsTester(self.tmp_path, registry=empty).send("ops")

    def test_public_response_ok_and_failed(self) -> None:
        ok_reg = NotificationRegistry()
        ok_reg.register(FakeStrategy("webhook"))
        NotificationsSettingsWriter(self.tmp_path, registry=ok_reg).create(
            {"id": "ops", "type": "webhook"}
        )
        tester = NotificationsTester(self.tmp_path, registry=ok_reg)
        ok = tester.public_response(tester.send("ops"))
        assert ok["ok"] is True
        assert ok["deliveries"][0]["status"] == "success"

        fail_reg = NotificationRegistry()
        fail_reg.register(
            FakeStrategy("webhook", result=DeliveryResult.failed("boom"))
        )
        bad = NotificationsTester(self.tmp_path, registry=fail_reg)
        payload = bad.public_response(bad.send("ops"))
        assert payload["ok"] is False
        assert "failed" in payload["message"]

    def test_public_response_empty(self) -> None:
        tester = NotificationsTester(self.tmp_path, registry=self._registry())
        payload = tester.public_response([])
        assert payload["ok"] is False
        assert payload["message"] == "No deliverable channels"

    def test_require_skips_non_matching_channel(self) -> None:
        registry = self._registry()
        writer = NotificationsSettingsWriter(self.tmp_path, registry=registry)
        writer.create({"id": "other", "type": "webhook"})
        writer.create({"id": "ops", "type": "webhook"})
        deliveries = NotificationsTester(
            self.tmp_path, registry=registry
        ).send("ops")
        assert deliveries[0].channel_id == "ops"
