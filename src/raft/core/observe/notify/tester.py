"""Send a safe probe ``NotificationEvent`` through one configured channel."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.types import NotificationChannelConfig
from raft.core.core.errors.cta import OperatorError

from .catalogs import NotificationCatalogs
from .channel import ChannelDescriptor
from .channel_delivery import ChannelDelivery
from .delivery_status import DeliveryStatus
from .dispatcher import NotificationDispatcher
from .event import NotificationEvent
from .registry import NotificationRegistry
from .severity import NotificationSeverity

KIND_NOTIFICATIONS_TEST = "notifications.test"


class NotificationsTester:
    """Fire a probe to one channel (force-enabled for the dispatch pass)."""

    def __init__(
        self,
        home: Path,
        *,
        registry: Optional[NotificationRegistry] = None,
        dispatcher: Optional[NotificationDispatcher] = None,
    ) -> None:
        self._home = home
        self._registry = (
            registry if registry is not None else NotificationCatalogs.default()
        )
        self._dispatcher = (
            dispatcher
            if dispatcher is not None
            else NotificationDispatcher(self._registry)
        )

    def send(self, channel_id: str) -> List[ChannelDelivery]:
        channel = self._require(channel_id)
        self._ensure_registered(channel)
        desc = ChannelDescriptor(
            channel_id=channel.id,
            type_id=channel.type,
            enabled=True,
            settings=dict(channel.settings),
        )
        return self._dispatcher.dispatch(self._probe(channel.id), [desc])

    def public_response(
        self, deliveries: Sequence[ChannelDelivery]
    ) -> Dict[str, Any]:
        rows = [
            {
                "channel_id": item.channel_id,
                "type_id": item.type_id,
                "status": item.result.status.value,
                "error": item.result.error,
            }
            for item in deliveries
        ]
        ok = any(d.result.status == DeliveryStatus.SUCCESS for d in deliveries)
        return {
            "ok": ok,
            "deliveries": rows,
            "message": self._message(deliveries, ok=ok),
        }

    def _require(self, channel_id: str) -> NotificationChannelConfig:
        cfg = SettingsLoader().load(self._home).notifications
        for channel in cfg.channels:
            if channel.id == channel_id:
                return channel
        raise KeyError(channel_id)

    def _ensure_registered(self, channel: NotificationChannelConfig) -> None:
        try:
            self._registry.get(channel.type)
        except OperatorError as exc:
            raise OperatorError(
                f"notification channel {channel.id!r}: {exc}",
                has_fix=False,
            ) from exc

    @staticmethod
    def _probe(channel_id: str) -> NotificationEvent:
        return NotificationEvent(
            kind=KIND_NOTIFICATIONS_TEST,
            severity=NotificationSeverity.INFO,
            title="raft notification test",
            body=(
                f"This is a test notification from raft "
                f"(channel {channel_id})."
            ),
            context={"channel_id": channel_id, "source": KIND_NOTIFICATIONS_TEST},
        )

    @staticmethod
    def _message(deliveries: Sequence[ChannelDelivery], *, ok: bool) -> str:
        if not deliveries:
            return "No deliverable channels"
        if ok:
            return f"Test sent via {deliveries[0].channel_id}"
        err = deliveries[0].result.error or "delivery failed"
        return f"Test failed for {deliveries[0].channel_id}: {err}"
