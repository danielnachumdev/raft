"""FastAPI handlers for ordered edge firewall (#211)."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from .apply import ServeFirewallService


class ServeFirewallApi:
    """Localhost JSON API over ordered firewall rules."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[ServeFirewallService] = None,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self.stack = stack
        self._service = service or ServeFirewallService(
            stack, orchestrator=orchestrator
        )

    def register(self, app) -> None:
        app.get("/api/firewall")(self.api_get)
        app.put("/api/firewall")(self.api_put)
        app.get("/api/firewall/export")(self.api_export)
        app.post("/api/firewall/import")(self.api_import)
        app.get("/api/firewall/services")(self.api_services)
        app.get("/api/firewall/recommendations")(self.api_recommendations)
        app.post("/api/firewall/recommendations/{recommendation_id}/dismiss")(
            self.api_dismiss
        )

    def api_get(self) -> Dict[str, Any]:
        return self._service.get()

    def api_put(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._service.put(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_export(self) -> Dict[str, Any]:
        return self._service.export_document()

    def api_import(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._service.import_document(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_services(self) -> Dict[str, Any]:
        return self._service.services()

    def api_recommendations(self) -> Dict[str, Any]:
        return self._service.recommendations()

    def api_dismiss(self, recommendation_id: str) -> Dict[str, Any]:
        return self._service.dismiss_recommendation(recommendation_id)

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
