"""Fan-out dispatcher: enabled channels → strategy → deliver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from .channel import ChannelDescriptor
from .event import DeliveryResult, NotificationEvent
from .registry import NotificationRegistry
from .strategy import NotificationStrategy


@dataclass(frozen=True)
class ChannelDelivery:
    """Outcome for one channel after a dispatch pass."""

    channel_id: str
    type_id: str
    result: DeliveryResult


class NotificationDispatcher:
    """Resolve channel descriptors through the registry; isolate per-channel failures."""

    def __init__(self, registry: NotificationRegistry) -> None:
        self._registry = registry

    def dispatch(
        self,
        event: NotificationEvent,
        channels: Sequence[ChannelDescriptor],
    ) -> List[ChannelDelivery]:
        return [self._one(event, channel) for channel in channels]

    def _one(
        self,
        event: NotificationEvent,
        channel: ChannelDescriptor,
    ) -> ChannelDelivery:
        if not channel.enabled:
            return self._wrap(channel, DeliveryResult.skipped("channel disabled"))
        strategy = self._registry.get(channel.type_id)
        return self._wrap(channel, self._deliver(strategy, event, channel))

    def _deliver(
        self,
        strategy: NotificationStrategy,
        event: NotificationEvent,
        channel: ChannelDescriptor,
    ) -> DeliveryResult:
        try:
            strategy.validate_settings(channel.settings)
            return strategy.deliver(event, channel.settings)
        except Exception as exc:
            return DeliveryResult.failed(self._safe_error(exc))

    def _wrap(
        self,
        channel: ChannelDescriptor,
        result: DeliveryResult,
    ) -> ChannelDelivery:
        return ChannelDelivery(channel.channel_id, channel.type_id, result)

    @staticmethod
    def _safe_error(exc: BaseException) -> str:
        """Operator-safe message: type name only (never settings / secret payloads)."""
        return f"{type(exc).__name__}: delivery failed"
