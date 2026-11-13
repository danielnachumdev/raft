"""Persist notification channel CRUD into ``~/.raft/host/notifications.yaml``."""

import errno
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import yaml

from raft.core.core.config.paths.host_paths import HostPaths
from raft.core.core.config.settings.strategies.notifications import (
    NotificationsSettingsParser,
)
from raft.core.core.config.settings.types import (
    NotificationChannelConfig,
    NotificationsConfig,
)
from raft.core.core.errors.cta import OperatorError
from raft.core.core.gitops.notifications_document import NotificationsDocument
from raft.core.core.gitops.notifications_gitops import NotificationsGitops
from raft.core.observe.notify.catalogs import NotificationCatalogs
from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_redactor import SettingsRedactor
from raft.core.platform.locking import SettingsLock


class NotificationsSettingsWriter:
    """Merge notification channels into ``host/notifications.yaml`` under flock."""

    def __init__(
        self,
        data_home: Path,
        *,
        registry: Optional[NotificationRegistry] = None,
    ) -> None:
        self._home = data_home
        self._path = HostPaths(data_home).notifications()
        self._parser = NotificationsSettingsParser()
        self._redactor = SettingsRedactor()
        self._registry = registry or NotificationCatalogs.default()
        self._gitops = NotificationsGitops(data_home)

    def list_public(self) -> Dict[str, Any]:
        cfg = self._load()
        return {
            "enabled": cfg.enabled,
            "channels": [self._public(ch) for ch in cfg.channels],
        }

    def get_public(self, channel_id: str) -> Dict[str, Any]:
        return self._public(self._require(self._load(), channel_id))

    def create(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        with SettingsLock(self._home):
            cfg = self._load()
            channel = self._channel_from_body(body, path="create")
            self._reject_duplicate(cfg, channel.id)
            self._maybe_validate(channel)
            next_cfg = self._with_channels(cfg, list(cfg.channels) + [channel])
            self._persist(next_cfg)
            return self._public(channel)

    def update(self, channel_id: str, body: Mapping[str, Any]) -> Dict[str, Any]:
        with SettingsLock(self._home):
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
        with SettingsLock(self._home):
            cfg = self._load()
            self._require(cfg, channel_id)
            kept = [ch for ch in cfg.channels if ch.id != channel_id]
            self._persist(self._with_channels(cfg, kept))

    def replace_config(self, cfg: NotificationsConfig) -> None:
        """Replace the whole destinations document (settings Save path)."""
        with SettingsLock(self._home):
            self._persist(cfg)

    def _load(self) -> NotificationsConfig:
        return self._gitops.load().config

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
        payload = NotificationsDocument(config=cfg).to_export()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(payload, sort_keys=False)
        try:
            self._path.write_text(text, encoding="utf-8")
            os.chmod(self._path, 0o600)
        except OSError as exc:
            self._raise_persist_os_error(exc)
        self._gitops.clear_cache()

    def _raise_persist_os_error(self, exc: OSError) -> None:
        if exc.errno == errno.EROFS:
            raise OperatorError(
                "cannot write host/notifications.yaml "
                "(dashboard data home is read-only).\n"
                "Fix: raft update && raft redeploy dashboard, then retry",
                has_fix=False,
            ) from exc
        raise OperatorError(
            f"cannot write host/notifications.yaml: {exc}.\n"
            "Fix: check permissions on ~/.raft/host/notifications.yaml",
            has_fix=False,
        ) from exc
