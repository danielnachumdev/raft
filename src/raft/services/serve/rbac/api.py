"""FastAPI handlers for ``host/rbac.yaml`` (#307)."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.rbac import PermissionCodes
from raft.core.core.rbac.writer import RbacDocumentWriter


class ServeRbacApi:
    """Localhost JSON API over RBAC document."""

    def __init__(
        self,
        stack: Stack,
        *,
        writer: Optional[RbacDocumentWriter] = None,
    ) -> None:
        self.stack = stack
        self._writer = writer or RbacDocumentWriter(stack.root)

    def register(self, app) -> None:
        app.get("/api/rbac")(self.api_get)
        app.put("/api/rbac")(self.api_put)
        app.get("/api/rbac/catalog")(self.api_catalog)

    def api_get(self) -> Dict[str, Any]:
        return self._writer.get()

    def api_put(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._writer.put(body)
        except OperatorError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @staticmethod
    def api_catalog() -> Dict[str, Any]:
        return {"permissions": list(PermissionCodes.catalog())}
