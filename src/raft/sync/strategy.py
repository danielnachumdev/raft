"""SyncStrategy ABC — subclass + register to add an App source kind."""

from abc import ABC, abstractmethod

from ..models.app import App

from .context import SyncContext


class SyncStrategy(ABC):
    """Open-closed source sync. Callers select via type_id, then dispatch."""

    @property
    @abstractmethod
    def type_id(self) -> str:
        """Stable discriminator matched by ``spec.source``."""

    @abstractmethod
    def sync(self, app: App, ctx: SyncContext) -> None:
        """Refresh one App's source under the data home."""
