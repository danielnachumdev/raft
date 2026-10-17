"""Notifier adapter honoring per-rule channel routing."""

from raft.core.observe.notify.event import NotificationEvent
from raft.core.observe.notify.notifier import Notifier

from ..model.rule import AlertRule


class AlertDispatch:
    """Send alert events through Notifier with optional channel filter."""

    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier

    def send(self, rule: AlertRule, event: NotificationEvent) -> None:
        ids = rule.channel_ids or None
        self._notifier.notify(event, channel_ids=ids)
