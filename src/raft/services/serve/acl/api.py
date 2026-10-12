"""FastAPI handlers for gate + per-app ACL CRUD."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from .apply import ServeAclService


class ServeAclApi:
    """Localhost JSON API over durable IP/CIDR ACL (gate + Apps)."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[ServeAclService] = None,
        orchestrator: Optional[Orchestrator] = None,
    ) -> None:
        self.stack = stack
        self._service = service or ServeAclService(stack, orchestrator=orchestrator)

    def register(self, app) -> None:
        app.get("/api/acl/gate")(self.api_gate_get)
        app.put("/api/acl/gate")(self.api_gate_put)
        app.delete("/api/acl/gate")(self.api_gate_delete)
        app.get("/api/acl/apps/{name}")(self.api_app_get)
        app.get("/api/acl/apps/{name}/meta")(self.api_app_meta)
        app.put("/api/acl/apps/{name}")(self.api_app_put)
        app.delete("/api/acl/apps/{name}")(self.api_app_delete)

    def api_gate_get(self) -> Dict[str, Any]:
        return self._service.gate_get()

    def api_gate_put(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._service.gate_put(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_gate_delete(self) -> Dict[str, Any]:
        try:
            return self._service.gate_clear()
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_app_meta(self, name: str) -> Dict[str, Any]:
        return self._service.app_meta(name)

    def api_app_get(self, name: str) -> Dict[str, Any]:
        try:
            return self._service.app_get(name)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_app_put(
        self, name: str, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        try:
            return self._service.app_put(name, body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_app_delete(self, name: str) -> Dict[str, Any]:
        try:
            return self._service.app_clear(name)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
