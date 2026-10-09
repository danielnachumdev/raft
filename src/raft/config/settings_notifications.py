"""Parse ``notifications:`` from settings.yaml."""

from __future__ import annotations

from typing import Any, Mapping

from raft.errors.cta import OperatorError

from .settings_types import NotificationChannelConfig, NotificationsConfig


class NotificationsSettingsParser:
    """Structural parse for durable notification channels (no strategy registry)."""

    def parse(self, raw: Any) -> NotificationsConfig:
        if raw is None:
            return NotificationsConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml notifications must be a mapping.\n"
                "Fix: set notifications: {enabled: true, channels: [...]} "
                "in ~/.raft/settings.yaml",
                has_fix=False,
            )
        return NotificationsConfig(
            enabled=bool(raw.get("enabled", True)),
            channels=self._channels(raw.get("channels")),
        )

    def _channels(self, raw: Any) -> tuple[NotificationChannelConfig, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise OperatorError(
                "settings.yaml notifications.channels must be a list.\n"
                "Fix: set notifications.channels: [{id: …, type: …}] "
                "in ~/.raft/settings.yaml",
                has_fix=False,
            )
        channels = [self._one(item, index) for index, item in enumerate(raw)]
        self._assert_unique_ids(channels)
        return tuple(channels)

    def _one(self, raw: Any, index: int) -> NotificationChannelConfig:
        path = f"notifications.channels[{index}]"
        if not isinstance(raw, dict):
            raise OperatorError(
                f"settings.yaml {path} must be a mapping.\n"
                f"Fix: use {{id: ops-primary, type: webhook, settings: {{…}}}}",
                has_fix=False,
            )
        return NotificationChannelConfig(
            id=self._required_id(raw, path),
            type=self._required_type(raw, path),
            enabled=bool(raw.get("enabled", True)),
            settings=self._settings_map(raw.get("settings"), path),
        )

    @staticmethod
    def _required_id(raw: Mapping[str, Any], path: str) -> str:
        value = str(raw.get("id") or "").strip()
        if not value:
            raise OperatorError(
                f"settings.yaml {path}.id is required.\n"
                f"Fix: set a unique id (e.g. ops-primary) on each channel",
                has_fix=False,
            )
        return value

    @staticmethod
    def _required_type(raw: Mapping[str, Any], path: str) -> str:
        value = str(raw.get("type") or "").strip()
        if not value:
            raise OperatorError(
                f"settings.yaml {path}.type is required.\n"
                f"Fix: set type to a strategy id (e.g. webhook) — "
                f"unknown types are allowed until a strategy is registered",
                has_fix=False,
            )
        return value

    @staticmethod
    def _settings_map(raw: Any, path: str) -> dict[str, Any]:
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise OperatorError(
                f"settings.yaml {path}.settings must be a mapping.\n"
                f"Fix: set settings: {{url: https://hooks.example.invalid/…}}",
                has_fix=False,
            )
        return dict(raw)

    @staticmethod
    def _assert_unique_ids(channels: list[NotificationChannelConfig]) -> None:
        seen: set[str] = set()
        for channel in channels:
            if channel.id in seen:
                raise OperatorError(
                    f"settings.yaml notifications.channels duplicate id "
                    f"{channel.id!r}.\n"
                    f"Fix: give each channel a unique id in ~/.raft/settings.yaml",
                    has_fix=False,
                )
            seen.add(channel.id)
