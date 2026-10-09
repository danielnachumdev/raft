"""Bridge ``NotificationsConfig`` → dispatcher ``ChannelDescriptor`` list."""

from __future__ import annotations

from typing import List

from raft.config.settings_types import NotificationChannelConfig, NotificationsConfig
from raft.errors.cta import OperatorError

from .channel import ChannelDescriptor
from .registry import NotificationRegistry


class NotifyConfigAdapter:
    """Adapt durable settings into dispatcher input; optional strategy validate."""

    def descriptors(self, config: NotificationsConfig) -> List[ChannelDescriptor]:
        if not config.enabled:
            return [
                ChannelDescriptor(
                    channel_id=ch.id,
                    type_id=ch.type,
                    enabled=False,
                    settings=dict(ch.settings),
                )
                for ch in config.channels
            ]
        return [self._one(ch) for ch in config.channels]

    def validate_registered(
        self,
        config: NotificationsConfig,
        registry: NotificationRegistry,
    ) -> None:
        """Validate settings for types present in the registry (dispatch-time)."""
        for channel in config.channels:
            self._validate_one(channel, registry)

    def _validate_one(
        self,
        channel: NotificationChannelConfig,
        registry: NotificationRegistry,
    ) -> None:
        try:
            strategy = registry.get(channel.type)
        except OperatorError as exc:
            raise OperatorError(
                f"notification channel {channel.id!r}: {exc}",
                has_fix=False,
            ) from exc
        strategy.validate_settings(channel.settings)

    @staticmethod
    def _one(channel: NotificationChannelConfig) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=channel.id,
            type_id=channel.type,
            enabled=channel.enabled,
            settings=dict(channel.settings),
        )
