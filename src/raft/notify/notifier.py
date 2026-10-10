"""Safe ``notify(event)`` entrypoint for control-plane producers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Sequence

from raft.config.settings import load_config

from .catalogs import NotificationCatalogs
from .channel import ChannelDescriptor
from .config_adapt import NotifyConfigAdapter
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

    def notify(self, event: NotificationEvent) -> None:
        try:
            self._dispatch(event)
        except Exception:  # noqa: BLE001 — producers must not crash the controller
            logger.exception("notification dispatch failed kind=%s", event.kind)

    def _dispatch(self, event: NotificationEvent) -> None:
        config = load_config(self._home).notifications
        if not config.enabled:
            return
        channels = self._deliverable(self._adapt.descriptors(config))
        if not channels:
            return
        self._dispatcher.dispatch(event, channels)

    def _deliverable(
        self, channels: Sequence[ChannelDescriptor]
    ) -> List[ChannelDescriptor]:
        known = {item["type_id"] for item in self._registry.catalog()}
        return [c for c in channels if c.enabled and c.type_id in known]
