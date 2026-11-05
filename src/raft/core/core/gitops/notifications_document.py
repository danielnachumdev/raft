"""Standalone ``notifications.yaml`` document (#310 / #317)."""

from dataclasses import dataclass
from typing import Any

from raft.core.core.config.settings.strategies.notifications import (
    NotificationsSettingsParser,
)
from raft.core.core.config.settings.types import NotificationsConfig


@dataclass(frozen=True)
class NotificationsDocument:
    """Same channel shape as settings ``notifications:``; flat-file SoT."""

    config: NotificationsConfig

    @classmethod
    def empty(cls) -> "NotificationsDocument":
        return cls(config=NotificationsConfig())

    @classmethod
    def from_mapping(cls, raw: Any, *, path: str) -> "NotificationsDocument":
        del path
        return cls(config=NotificationsSettingsParser().parse(raw))

    def to_export(self) -> dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "channels": [
                {
                    "id": channel.id,
                    "type": channel.type,
                    "enabled": channel.enabled,
                    "settings": dict(channel.settings),
                }
                for channel in self.config.channels
            ],
        }
