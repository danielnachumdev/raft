"""Serve notification API routes (redacted; no live delivery clients)."""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

import yaml
from fastapi.testclient import TestClient

from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_write import NotificationsSettingsWriter
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.services.serve.http.app import ServeAppFactory
from raft.services.serve.notifications.api import ServeNotificationsApi

from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.ops.status import fixtures as status_fx
from tests.unit.core.observe.notify.fakes import FakeStrategy


class TestServeNotificationsApi(RaftTestCase):
    def _client(self, *, registry: Optional[NotificationRegistry] = None) -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        api = ServeNotificationsApi(stack, registry=registry or NotificationRegistry())
        return TestClient(
            ServeAppFactory(stack, status=status, notifications=api).create()
        )

    def test_empty_list_and_catalog(self) -> None:
        client = self._client()
        assert client.get("/api/notifications/strategies").json() == {
            "strategies": []
        }
        assert client.get("/api/notifications/channels").json() == {
            "enabled": True,
            "channels": [],
        }

    def test_default_catalog_lists_shipped_types(self) -> None:
        client = self._default_catalog_client()
        types = [
            row["type_id"]
            for row in client.get("/api/notifications/strategies").json()["strategies"]
        ]
        assert types == ["webhook", "email", "whatsapp"]
        catalog = client.get("/api/notifications/strategies").json()["strategies"]
        whatsapp = next(row for row in catalog if row["type_id"] == "whatsapp")
        assert whatsapp["label"] == "WhatsApp (GREEN-API)"
        assert any(f["key"] == "apiTokenInstance" for f in whatsapp["fields"])
        bad = client.post(
            "/api/notifications/channels",
            json={"id": "ops", "type": "email", "settings": {}},
        )
        assert bad.status_code == 400 and "settings.to" in bad.json()["detail"]

    def _default_catalog_client(self) -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        return TestClient(
            ServeAppFactory(
                stack, status=status, notifications=ServeNotificationsApi(stack)
            ).create()
        )

    def test_create_get_redacts_secrets(self) -> None:
        client = self._client()
        created = client.post(
            "/api/notifications/channels",
            json={
                "id": "ops-primary",
                "type": "webhook",
                "settings": {"token": "clear-secret", "to": "ops@example.com"},
            },
        )
        assert created.status_code == 200
        body = created.json()
        assert body["settings"]["token"] == "***"
        assert body["settings"]["to"] == "ops@example.com"
        assert "clear-secret" not in created.text
        got = client.get("/api/notifications/channels/ops-primary").json()
        assert got["settings"]["token"] == "***"

    def test_update_enable_and_hard_delete(self) -> None:
        client = self._client()
        client.post(
            "/api/notifications/channels",
            json={"id": "ops-primary", "type": "webhook"},
        )
        disabled = client.put(
            "/api/notifications/channels/ops-primary",
            json={"enabled": False},
        ).json()
        assert disabled["enabled"] is False
        deleted = client.delete("/api/notifications/channels/ops-primary")
        assert deleted.status_code == 200 and deleted.json()["ok"] is True
        assert client.get("/api/notifications/channels").json()["channels"] == []

    def test_catalog_lists_registered_fakes(self) -> None:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        registry.register(FakeStrategy("email"))
        client = self._client(registry=registry)
        types = [
            row["type_id"]
            for row in client.get("/api/notifications/strategies").json()["strategies"]
        ]
        assert types == ["webhook", "email"]

    def test_missing_channel_is_404(self) -> None:
        client = self._client()
        assert client.get("/api/notifications/channels/missing").status_code == 404
        assert (
            client.put(
                "/api/notifications/channels/missing", json={"enabled": False}
            ).status_code
            == 404
        )
        assert client.delete("/api/notifications/channels/missing").status_code == 404
        assert (
            client.post("/api/notifications/channels/missing/test").status_code
            == 404
        )

    def test_send_test_uses_shared_tester(self) -> None:
        registry = NotificationRegistry()
        fake = FakeStrategy("webhook")
        registry.register(fake)
        client = self._client(registry=registry)
        client.post(
            "/api/notifications/channels",
            json={
                "id": "ops-webhook",
                "type": "webhook",
                "enabled": False,
                "settings": {"url": "https://example.invalid/hooks/demo-api"},
            },
        )
        response = client.post("/api/notifications/channels/ops-webhook/test")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["deliveries"][0]["channel_id"] == "ops-webhook"
        assert fake.delivered[0].kind == "notifications.test"

    def test_send_test_unknown_type_is_400(self) -> None:
        client = self._client_with_disk_channel()
        response = client.post("/api/notifications/channels/ops/test")
        assert response.status_code == 400
        assert "ops" in response.json()["detail"]

    def _client_with_disk_channel(self) -> TestClient:
        stack = StackMakers.make_stack(self.tmp_path)
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        NotificationsSettingsWriter(self.tmp_path).create(
            {
                "id": "ops",
                "type": "webhook",
                "settings": {"url": "https://example.invalid/hooks/demo-api"},
            }
        )
        status = MagicMock()
        status.collect.return_value = StatusSnapshot(
            host=status_fx.empty_host_status(), containers=()
        )
        api = ServeNotificationsApi(stack, registry=NotificationRegistry())
        return TestClient(
            ServeAppFactory(stack, status=status, notifications=api).create()
        )

    def test_invalid_create_is_400(self) -> None:
        client = self._client()
        response = client.post("/api/notifications/channels", json={"type": "webhook"})
        assert response.status_code == 400
        assert "id is required" in response.json()["detail"]

    def test_invalid_update_is_400(self) -> None:
        client = self._client()
        client.post(
            "/api/notifications/channels",
            json={"id": "ops", "type": "webhook"},
        )
        response = client.put(
            "/api/notifications/channels/ops",
            json={"settings": []},
        )
        assert response.status_code == 400
        assert "settings must be" in response.json()["detail"]

    def test_persists_to_settings_yaml(self) -> None:
        client = self._client()
        client.post(
            "/api/notifications/channels",
            json={
                "id": "ops",
                "type": "webhook",
                "settings": {"token": "disk-secret"},
            },
        )
        raw = yaml.safe_load((self.tmp_path / "host" / "settings.yaml").read_text())
        assert raw["notifications"]["channels"][0]["settings"]["token"] == "disk-secret"
        listed = client.get("/api/notifications/channels").json()["channels"][0]
        assert listed["settings"]["token"] == "***"
        assert "disk-secret" not in str(listed)
