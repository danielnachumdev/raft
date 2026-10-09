"""Test doubles for notify (no network / SMTP / third-party APIs)."""

from __future__ import annotations

from typing import Any, List, Mapping, Optional

from raft.errors.cta import OperatorError
from raft.services.notify.event import DeliveryResult, NotificationEvent
from raft.services.notify.strategy import NotificationStrategy


class FakeStrategy(NotificationStrategy):
    """Records deliver calls; optional soft failure or raised exception."""

    def __init__(
        self,
        type_id: str,
        *,
        result: Optional[DeliveryResult] = None,
        raise_on_deliver: Optional[BaseException] = None,
        reject_settings: bool = False,
    ) -> None:
        self._type_id = type_id
        self._result = result or DeliveryResult.success()
        self._raise_on_deliver = raise_on_deliver
        self._reject_settings = reject_settings
        self.delivered: List[NotificationEvent] = []

    @property
    def type_id(self) -> str:
        return self._type_id

    def validate_settings(self, settings: Mapping[str, Any]) -> None:
        if self._reject_settings:
            raise OperatorError(
                "fake settings rejected.\nFix: use demo settings",
            )

    def deliver(
        self,
        event: NotificationEvent,
        settings: Mapping[str, Any],
    ) -> DeliveryResult:
        if self._raise_on_deliver is not None:
            raise self._raise_on_deliver
        self.delivered.append(event)
        return self._result
