"""NotificationStrategy ABC — subclass + register to add a channel type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from .event import DeliveryResult, NotificationEvent


class NotificationStrategy(ABC):
    """Open-closed delivery backend. Callers never branch on concrete types."""

    @property
    @abstractmethod
    def type_id(self) -> str:
        """Stable type discriminator matched by channel descriptors."""

    @abstractmethod
    def validate_settings(self, settings: Mapping[str, Any]) -> None:
        """Raise OperatorError when settings are invalid for this type."""

    @abstractmethod
    def deliver(
        self,
        event: NotificationEvent,
        settings: Mapping[str, Any],
    ) -> DeliveryResult:
        """Attempt delivery. Return failed with a safe error string on soft failure."""
