"""FastAPI handlers for ordered edge firewall (#211)."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException, Query

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.lifecycle.firewall import FirewallService
from raft.services.serve.auth.route_deps import RouteRbacDeps


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
        app.state.raft_home = self.stack.root
        d = RouteRbacDeps("firewall")
        self._register_reads(app, d)
        self._register_writes(app, d)

    def _register_reads(self, app, d: RouteRbacDeps) -> None:
        d.get(app, "/api/firewall", self.api_get)
        d.get(app, "/api/firewall/export", self.api_export)
        d.get(app, "/api/firewall/services", self.api_services)
        d.get(app, "/api/firewall/recommendations", self.api_recommendations)
        d.get(app, "/api/firewall/from-inspection", self.api_inspection_draft)

    def _register_writes(self, app, d: RouteRbacDeps) -> None:
        d.mut(app, "put", "/api/firewall", self.api_put)
        d.mut(app, "post", "/api/firewall/import", self.api_import)
        d.mut(
            app,
            "post",
            "/api/firewall/recommendations/{recommendation_id}/dismiss",
            self.api_dismiss,
        )
        d.mut(app, "post", "/api/firewall/from-inspection", self.api_from_inspection)
        d.mut(
            app,
            "post",
            "/api/firewall/from-inspection/remove",
            self.api_remove_inspection,
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
