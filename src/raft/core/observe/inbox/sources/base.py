"""ABC for operator-inbox feed sources."""

from abc import ABC, abstractmethod
from typing import List

from raft.core.observe.inbox.item import InboxItem


class InboxSource(ABC):
    """One heterogeneous origin that can list (and maybe dismiss) items."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Stable source kind used in item ids (e.g. ``firewall-recommendation``)."""

    @abstractmethod
    def list_items(self) -> List[InboxItem]:
        """Derived feed rows; unread is filled by the inbox service."""

    def dismiss(self, source_item_id: str) -> None:
        """Dismiss via the source SoT when supported; default is unsupported."""
        raise NotImplementedError(self.source_id)
