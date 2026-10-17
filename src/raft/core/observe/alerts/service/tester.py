"""Send alert.test through Notifier.deliver for a rule."""

from pathlib import Path
from typing import List

from raft.core.observe.notify.channel_delivery import ChannelDelivery
from raft.core.observe.notify.notifier import Notifier

from ..catalogs import AlertCatalogs
from ..engine.event_factory import AlertEventFactory
from ..store.rules_store import AlertRulesStore


class AlertTester:
    """Fire a test notification for one rule."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._store = AlertRulesStore(home, registries=AlertCatalogs.default())
        self._notifier = Notifier(home)
        self._events = AlertEventFactory()

    def send(self, rule_id: str) -> List[ChannelDelivery]:
        rule = self._store.load().get(rule_id)
        if rule is None:
            raise KeyError(rule_id)
        event = self._events.test(rule)
        return self._notifier.deliver(
            event, channel_ids=rule.channel_ids or None
        )
