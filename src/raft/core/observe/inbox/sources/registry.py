"""Default inbox source wiring (firewall + optional alerts)."""

from pathlib import Path
from typing import List, Optional, Sequence

from raft.core.observe.inbox.sources.alerts import AlertsInboxSource
from raft.core.observe.inbox.sources.base import InboxSource
from raft.core.observe.inbox.sources.firewall import FirewallInboxSource


class InboxSourceRegistry:
    """Enumerate configured inbox sources for a data home."""

    @staticmethod
    def default(
        home: Path,
        *,
        extra: Optional[Sequence[InboxSource]] = None,
    ) -> List[InboxSource]:
        sources: List[InboxSource] = [FirewallInboxSource(home)]
        alerts = AlertsInboxSource.try_create(home)
        if alerts is not None:
            sources.append(alerts)
        if extra:
            sources.extend(extra)
        return sources
