"""FastAPI handlers for ordered edge firewall (#211)."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException, Query

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.lifecycle.firewall import FirewallService


class ServeFirewallApi:
    """Localhost JSON API over ordered firewall rules."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[FirewallService] = None,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self.stack = stack
        self._service = service or FirewallService(
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
        app.get("/api/firewall/from-inspection")(self.api_inspection_draft)
        app.post("/api/firewall/from-inspection")(self.api_from_inspection)
        app.post("/api/firewall/from-inspection/remove")(
            self.api_remove_inspection
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

    def api_inspection_draft(
        self,
        client_ip: str = Query(...),
        service: str = Query(""),
        action: str = Query("deny"),
    ) -> Dict[str, Any]:
        try:
            return self._service.inspection_draft(
                client_ip=client_ip, service=service, action=action
            )
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_from_inspection(
        self, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        try:
            return self._service.apply_from_inspection(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_remove_inspection(
        self, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        try:
            return self._service.remove_from_inspection(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
