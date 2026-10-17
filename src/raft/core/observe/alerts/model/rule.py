"""Alert rule model."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from raft.core.observe.notify.severity import NotificationSeverity

from .condition import ConditionNode


@dataclass(frozen=True)
class AlertRule:
    """One durable alert rule."""

    id: str
    name: str
    enabled: bool
    severity: NotificationSeverity
    description: str
    for_seconds: int
    cooldown_seconds: int
    repeat_every_seconds: int
    notify_on_recovery: bool
    no_data: str
    channel_ids: Tuple[str, ...]
    condition: ConditionNode

    def to_export(self) -> Dict[str, Any]:
        from .duration import AlertDuration

        return {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "severity": self.severity.value,
            "description": self.description,
            "for": AlertDuration.format(self.for_seconds),
            "cooldown": AlertDuration.format(self.cooldown_seconds),
            "repeatEvery": AlertDuration.format(self.repeat_every_seconds),
            "notifyOnRecovery": self.notify_on_recovery,
            "noData": self.no_data,
            "channelIds": list(self.channel_ids),
            "condition": self.condition.to_export(),
        }

    def to_public(self) -> Dict[str, Any]:
        return self.to_export()
