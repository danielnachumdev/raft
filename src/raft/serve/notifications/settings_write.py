"""Persist ``notifications:`` channel CRUD into ``~/.raft/settings.yaml``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from raft.config.paths import settings_path
from raft.config.settings import load_config
from raft.config.settings_notifications import NotificationsSettingsParser
from raft.config.settings_types import NotificationChannelConfig, NotificationsConfig
from raft.errors.cta import OperatorError
from raft.locking.locking import notifications_lock
from raft.notify.catalogs import NotificationCatalogs
from raft.notify.redact import SettingsRedactor
from raft.notify.registry import NotificationRegistry


class NotificationsSettingsWriter:
    """Merge notification channels into operator settings under flock."""

    def __init__(
        self,
        data_home: Path,
        *,
        registry: Optional[NotificationRegistry] = None,
    ) -> None:
        self._home = data_home
        self._path = settings_path(data_home)
        self._parser = NotificationsSettingsParser()
        self._redactor = SettingsRedactor()
        self._registry = registry or NotificationCatalogs.default()

    def list_public(self) -> Dict[str, Any]:
        cfg = self._load()
        return {
            "enabled": cfg.enabled,
            "channels": [self._public(ch) for ch in cfg.channels],
        }

    def get_public(self, channel_id: str) -> Dict[str, Any]:
        return self._public(self._require(self._load(), channel_id))

    def create(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with notifications_lock(self._home):
            cfg = self._load()
            channel = self._channel_from_body(body, path="create")
            self._reject_duplicate(cfg, channel.id)
            self._maybe_validate(channel)
            next_cfg = self._with_channels(cfg, list(cfg.channels) + [channel])
            self._persist(next_cfg)
            return self._public(channel)

    def update(self, channel_id: str, body: Mapping[str, Any]) -> Dict[str, Any]:
        with notifications_lock(self._home):
            cfg = self._load()
            current = self._require(cfg, channel_id)
            updated = self._merge_channel(current, body)
            self._maybe_validate(updated)
            channels = [
                updated if ch.id == channel_id else ch for ch in cfg.channels
            ]
            self._persist(self._with_channels(cfg, channels))
            return self._public(updated)

    def delete(self, channel_id: str) -> None:
        with notifications_lock(self._home):
            cfg = self._load()
            self._require(cfg, channel_id)
            kept = [ch for ch in cfg.channels if ch.id != channel_id]
            self._persist(self._with_channels(cfg, kept))

    def _load(self) -> NotificationsConfig:
        return load_config(self._home).notifications

    def _public(self, channel: NotificationChannelConfig) -> Dict[str, Any]:
        return {
            "id": channel.id,
            "type": channel.type,
            "enabled": channel.enabled,
            "settings": self._redactor.redact(channel.settings),
        }

    def _channel_from_body(
        self, body: Mapping[str, Any], *, path: str
    ) -> NotificationChannelConfig:
        if not isinstance(body, dict):
            raise OperatorError(
                f"notification channel {path} body must be a JSON object.\n"
                f"Fix: POST {{id, type, settings?, enabled?}}",
                has_fix=False,
            )
        return self._parser.parse({"channels": [self._raw_channel(body)]}).channels[0]

    def _merge_channel(
        self,
        current: NotificationChannelConfig,
        body: Mapping[str, Any],
    ) -> NotificationChannelConfig:
        if not isinstance(body, dict):
            raise OperatorError(
                "notification channel update body must be a JSON object.\n"
                "Fix: PUT {type?, enabled?, settings?}",
                has_fix=False,
            )
        if "id" in body and str(body["id"]).strip() not in ("", current.id):
            raise OperatorError(
                "notification channel id cannot be changed.\n"
                "Fix: delete and create a new channel, or omit id",
                has_fix=False,
            )
        raw = {
            "id": current.id,
            "type": body["type"] if "type" in body else current.type,
            "enabled": body["enabled"] if "enabled" in body else current.enabled,
            "settings": self._merged_settings(current, body),
        }
        return self._parser.parse({"channels": [raw]}).channels[0]

    def _merged_settings(
        self,
        current: NotificationChannelConfig,
        body: Mapping[str, Any],
    ) -> dict[str, Any]:
        if "settings" not in body:
            return dict(current.settings)
        incoming = body["settings"]
        if not isinstance(incoming, dict):
            raise OperatorError(
                "notification channel settings must be a JSON object.\n"
                "Fix: set settings: {…}",
                has_fix=False,
            )
        return self._redactor.merge_preserving_secrets(current.settings, incoming)

    def _maybe_validate(self, channel: NotificationChannelConfig) -> None:
        try:
            strategy = self._registry.get(channel.type)
        except OperatorError:
            return
        strategy.validate_settings(channel.settings)

    @staticmethod
    def _raw_channel(body: Mapping[str, Any]) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "id": body.get("id"),
            "type": body.get("type"),
            "enabled": body.get("enabled", True),
        }
        if "settings" in body:
            raw["settings"] = body["settings"]
        return raw

    @staticmethod
    def _reject_duplicate(cfg: NotificationsConfig, channel_id: str) -> None:
        if any(ch.id == channel_id for ch in cfg.channels):
            raise OperatorError(
                f"notification channel {channel_id!r} already exists.\n"
                f"Fix: choose a unique id, or PUT to update the existing channel",
                has_fix=False,
            )

    @staticmethod
    def _require(
        cfg: NotificationsConfig, channel_id: str
    ) -> NotificationChannelConfig:
        for channel in cfg.channels:
            if channel.id == channel_id:
                return channel
        raise KeyError(channel_id)

    @staticmethod
    def _with_channels(
        cfg: NotificationsConfig,
        channels: List[NotificationChannelConfig],
    ) -> NotificationsConfig:
        return NotificationsConfig(enabled=cfg.enabled, channels=tuple(channels))

    def _persist(self, cfg: NotificationsConfig) -> None:
        data = self._load_root()
        data["notifications"] = {
            "enabled": cfg.enabled,
            "channels": [self._channel_yaml(ch) for ch in cfg.channels],
        }
        self._write_root(data)

    @staticmethod
    def _channel_yaml(channel: NotificationChannelConfig) -> dict[str, Any]:
        return {
            "id": channel.id,
            "type": channel.type,
            "enabled": channel.enabled,
            "settings": dict(channel.settings),
        }

    def _load_root(self) -> Dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot update settings.yaml: {self._path}\n"
                f"Fix: repair ~/.raft/settings.yaml then retry from serve",
                has_fix=False,
            ) from exc
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml must be a YAML mapping.\n"
                "Fix: repair ~/.raft/settings.yaml",
                has_fix=False,
            )
        return raw

    def _write_root(self, data: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(dict(data), sort_keys=False)
        self._path.write_text(text, encoding="utf-8")
        os.chmod(self._path, 0o600)
