"""NotificationsSettingsWriter: CRUD + flock + redaction."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import yaml

from raft.config.settings import load_config
from raft.errors.cta import OperatorError
from raft.notify.registry import NotificationRegistry
from raft.serve.notifications.settings_write import (
    NotificationsSettingsWriter,
)

from tests.unit.base import RaftTestCase
from tests.unit.notify.fakes import FakeStrategy


class TestNotificationsSettingsWriter(RaftTestCase):
    def test_create_redacts_secrets_in_response(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        created = writer.create(self._secret_channel())
        assert created["settings"]["token"] == "***"
        assert "super-secret" not in str(created)
        assert "token=abc" not in created["settings"]["url"]
        assert created["settings"]["label"] == "ops"

    def test_list_get_redact_while_disk_keeps_secret(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(self._secret_channel())
        listed = writer.list_public()
        assert listed["enabled"] is True
        assert listed["channels"][0]["id"] == "ops-primary"
        assert writer.get_public("ops-primary")["settings"]["token"] == "***"
        loaded = load_config(self.tmp_path).notifications.channels[0]
        assert loaded.settings["token"] == "super-secret"

    @staticmethod
    def _channel(channel_id: str = "ops") -> dict:
        return {
            "id": channel_id,
            "type": "webhook",
            "settings": {"url": "https://hooks.example.invalid/raft"},
        }

    @staticmethod
    def _secret_channel() -> dict:
        return {
            "id": "ops-primary",
            "type": "webhook",
            "settings": {
                "url": "https://hooks.example.invalid/raft?token=abc",
                "token": "super-secret",
                "label": "ops",
            },
        }

    def test_update_enable_and_preserve_masked_secret(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(
            {
                "id": "ops",
                "type": "webhook",
                "settings": {"token": "keep-me", "url": "https://hooks.example.invalid/x"},
            }
        )
        out = writer.update(
            "ops",
            {"enabled": False, "settings": {"token": "***", "url": "https://hooks.example.invalid/y"}},
        )
        assert out["enabled"] is False
        assert out["settings"]["token"] == "***"
        assert load_config(self.tmp_path).notifications.channels[0].settings[
            "token"
        ] == "keep-me"

    def test_hard_delete(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(self._channel("a"))
        writer.create(self._email_channel("b"))
        writer.delete("a")
        ids = [c.id for c in load_config(self.tmp_path).notifications.channels]
        assert ids == ["b"]

    @staticmethod
    def _email_channel(channel_id: str = "oncall") -> dict:
        return {
            "id": channel_id,
            "type": "email",
            "settings": {
                "to": "ops@example.com",
                "from": "raft@example.com",
                "smtpHost": "smtp.example.com",
            },
        }

    def test_duplicate_and_missing(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(self._channel("ops"))
        with pytest.raises(OperatorError, match="already exists"):
            writer.create({"id": "ops", "type": "email"})
        with pytest.raises(KeyError):
            writer.get_public("missing")

    def test_registered_strategy_validates_settings(self) -> None:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook", reject_settings=True))
        writer = NotificationsSettingsWriter(self.tmp_path, registry=registry)
        with pytest.raises(OperatorError, match="fake settings rejected"):
            writer.create({"id": "ops", "type": "webhook", "settings": {}})

    def test_unknown_type_allowed(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        out = writer.create({"id": "x", "type": "future-backend"})
        assert out["type"] == "future-backend"

    def test_mutative_uses_notifications_lock(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        with patch(
            "raft.serve.notifications.settings_write.notifications_lock"
        ) as lock:
            lock.return_value.__enter__ = lambda s: None
            lock.return_value.__exit__ = lambda s, *a: None
            writer.create(self._channel("ops"))
            writer.update("ops", {"enabled": False})
            writer.delete("ops")
        assert lock.call_count == 3

    def test_preserves_other_settings_keys(self) -> None:
        path = self.tmp_path / "settings.yaml"
        path.write_text("edge: {http: 80}\n", encoding="utf-8")
        NotificationsSettingsWriter(self.tmp_path).create(self._channel("ops"))
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["edge"]["http"] == 80
        assert data["notifications"]["channels"][0]["id"] == "ops"

    def test_reject_id_change(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(self._channel("ops"))
        with pytest.raises(OperatorError, match="cannot be changed"):
            writer.update("ops", {"id": "other"})
        writer.update("ops", {"id": "ops"})
        writer.update("ops", {"id": ""})

    def test_reject_non_object_bodies(self) -> None:
        writer = NotificationsSettingsWriter(self.tmp_path)
        writer.create(self._channel("ops"))
        with pytest.raises(OperatorError, match="JSON object"):
            writer.create("nope")  # type: ignore[arg-type]
        with pytest.raises(OperatorError, match="JSON object"):
            writer.update("ops", "nope")  # type: ignore[arg-type]
        with pytest.raises(OperatorError, match="settings must be"):
            writer.update("ops", {"settings": []})

    def test_load_root_errors(self) -> None:
        path = self.tmp_path / "settings.yaml"
        path.unlink()
        writer = NotificationsSettingsWriter(self.tmp_path)
        assert writer._load_root() == {}
        path.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="YAML mapping"):
            writer._load_root()
        path.write_text("edge: {}\n", encoding="utf-8")
        with patch(
            "raft.serve.notifications.settings_write.yaml.safe_load",
            side_effect=yaml.YAMLError("bad"),
        ):
            with pytest.raises(OperatorError, match="cannot update"):
                writer._load_root()
