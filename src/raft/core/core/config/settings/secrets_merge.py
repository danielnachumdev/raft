"""Preserve masked secrets when a settings document is PUT from serve."""

from typing import Any, Mapping, Optional

from raft.core.observe.notify.settings_redactor import SettingsRedactor

from .types import GithubServeConfig, NotificationChannelConfig, NotificationsConfig


class SettingsSecretsMerge:
    """Re-apply stored secrets when the client sends the redaction mask."""

    def __init__(self) -> None:
        self._redactor = SettingsRedactor()

    def notifications(
        self,
        incoming: NotificationsConfig,
        prior: NotificationsConfig,
    ) -> NotificationsConfig:
        by_id = {ch.id: ch for ch in prior.channels}
        merged = [
            self._channel(ch, by_id.get(ch.id)) for ch in incoming.channels
        ]
        return NotificationsConfig(enabled=incoming.enabled, channels=tuple(merged))

    def _channel(
        self,
        incoming: NotificationChannelConfig,
        prior: Optional[NotificationChannelConfig],
    ) -> NotificationChannelConfig:
        if prior is None:
            return incoming
        settings = self._redactor.merge_preserving_secrets(
            prior.settings, dict(incoming.settings)
        )
        return NotificationChannelConfig(
            id=incoming.id,
            type=incoming.type,
            enabled=incoming.enabled,
            settings=settings,
        )

    def github(
        self,
        incoming: GithubServeConfig,
        prior: GithubServeConfig,
    ) -> GithubServeConfig:
        secret = incoming.client_secret
        if secret == SettingsRedactor._MASK and prior.client_secret:
            secret = prior.client_secret
        return GithubServeConfig(
            mock=incoming.mock,
            client_id=incoming.client_id,
            client_secret=secret,
            session_ttl_seconds=incoming.session_ttl_seconds,
        )

    def redact_document(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(raw)
        github = out.get("github")
        if isinstance(github, dict):
            out["github"] = self._redact_github(github)
        notifications = out.get("notifications")
        if isinstance(notifications, dict):
            out["notifications"] = self._redact_notifications(notifications)
        return out

    def _redact_github(self, github: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(github)
        if out.get("clientSecret"):
            out["clientSecret"] = SettingsRedactor._MASK
        return out

    def _redact_notifications(self, notifications: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(notifications)
        channels = out.get("channels")
        if not isinstance(channels, list):
            return out
        redacted = []
        for channel in channels:
            if not isinstance(channel, dict):
                redacted.append(channel)
                continue
            item = dict(channel)
            settings = item.get("settings")
            if isinstance(settings, dict):
                item["settings"] = self._redactor.redact(settings)
            redacted.append(item)
        out["channels"] = redacted
        return out
