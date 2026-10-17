"""FastAPI handlers for notification channel CRUD + strategy catalog."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.catalogs import NotificationCatalogs
from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_write import NotificationsSettingsWriter
from raft.core.observe.notify.tester import NotificationsTester


class ServeNotificationsApi:
    """Localhost JSON API over durable ``notifications:`` settings."""

    def __init__(
        self,
        stack: Stack,
        *,
        registry: Optional[NotificationRegistry] = None,
        writer: Optional[NotificationsSettingsWriter] = None,
        tester: Optional[NotificationsTester] = None,
    ) -> None:
        self.stack = stack
        self._registry = registry or NotificationCatalogs.default()
        self._settings = writer or NotificationsSettingsWriter(
            stack.root, registry=self._registry
        )
        self._tester = tester or NotificationsTester(
            stack.root, registry=self._registry
        )

    def register(self, app) -> None:
        app.get("/api/notifications/channels")(self.api_list)
        app.get("/api/notifications/channels/{channel_id}")(self.api_get)
        app.post("/api/notifications/channels")(self.api_create)
        app.put("/api/notifications/channels/{channel_id}")(self.api_update)
        app.delete("/api/notifications/channels/{channel_id}")(self.api_delete)
        app.post("/api/notifications/channels/{channel_id}/test")(self.api_test)
        app.get("/api/notifications/strategies")(self.api_strategies)

    def api_list(self) -> Dict[str, Any]:
        return self._settings.list_public()

    def api_get(self, channel_id: str) -> Dict[str, Any]:
        try:
            return self._settings.get_public(channel_id)
        except KeyError as exc:
            raise self._missing(channel_id) from exc

    def api_create(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._settings.create(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_update(
        self, channel_id: str, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        try:
            return self._settings.update(channel_id, body)
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_delete(self, channel_id: str) -> Dict[str, Any]:
        try:
            self._settings.delete(channel_id)
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        return {"ok": True, "deleted": channel_id}

    def api_test(self, channel_id: str) -> Dict[str, Any]:
        try:
            deliveries = self._tester.send(channel_id)
        except KeyError as exc:
            raise self._missing(channel_id) from exc
        except OperatorError as exc:
            raise self._bad(exc) from exc
        return self._tester.public_response(deliveries)

    def api_strategies(self) -> Dict[str, Any]:
        return {"strategies": self._registry.catalog()}

    @staticmethod
    def _missing(channel_id: str) -> HTTPException:
        return HTTPException(
            status_code=404,
            detail=(
                f"notification channel '{channel_id}' not found. "
                f"Fix: GET /api/notifications/channels"
            ),
        )

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
