"""Safe ``notify(event)`` entrypoint for control-plane producers."""

import logging
from pathlib import Path
from typing import List, Optional, Sequence

from raft.core.core.config.settings import SettingsLoader

from .catalogs import NotificationCatalogs
from .channel import ChannelDescriptor
from .channel_delivery import ChannelDelivery
from .config_adapter import NotifyConfigAdapter
from .dispatcher import NotificationDispatcher
from .event import NotificationEvent
from .registry import NotificationRegistry

logger = logging.getLogger(__name__)


class Notifier:
    """Load durable channels and fan out; no-op when disabled / empty / unknown types."""

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
        self._adapt = NotifyConfigAdapter()

    @property
    def registry(self) -> NotificationRegistry:
        return self._registry

    def notify(
        self,
        event: NotificationEvent,
        *,
        channel_ids: Optional[Sequence[str]] = None,
    ) -> None:
        try:
            self.deliver(event, channel_ids=channel_ids)
        except Exception:  # noqa: BLE001 — producers must not crash the controller
            logger.exception("notification dispatch failed kind=%s", event.kind)

    def deliver(
        self,
        event: NotificationEvent,
        *,
        channel_ids: Optional[Sequence[str]] = None,
    ) -> List[ChannelDelivery]:
        """Like notify, but returns per-channel results and may raise."""
        config = SettingsLoader().load(self._home).notifications
        if not config.enabled:
            return []
        channels = self._deliverable(
            self._adapt.descriptors(config), channel_ids=channel_ids
        )
        if not channels:
            return []
        return self._dispatcher.dispatch(event, channels)

    def _deliverable(
        self,
        channels: Sequence[ChannelDescriptor],
        *,
        channel_ids: Optional[Sequence[str]] = None,
    ) -> List[ChannelDescriptor]:
        known = {item["type_id"] for item in self._registry.catalog()}
        enabled = [c for c in channels if c.enabled and c.type_id in known]
        if not channel_ids:
            return enabled
        return self._filter_ids(enabled, channel_ids)

    def _filter_ids(
        self,
        channels: Sequence[ChannelDescriptor],
        channel_ids: Sequence[str],
    ) -> List[ChannelDescriptor]:
        by_id = {c.channel_id: c for c in channels}
        out: List[ChannelDescriptor] = []
        for channel_id in channel_ids:
            channel = by_id.get(channel_id)
            if channel is None:
                logger.warning(
                    "notification channel id %r not found or not deliverable",
                    channel_id,
                )
                continue
            out.append(channel)
        return out
