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
        app.post("/api/rbac/yaml/encode")(self.api_encode_yaml)
        app.post("/api/rbac/yaml/decode")(self.api_decode_yaml)

    def api_get(self) -> Dict[str, Any]:
        return self._writer.export_document()

    def api_put(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return self._call(lambda: self._writer.replace(body))

    @staticmethod
    def api_catalog() -> Dict[str, Any]:
        return {"permissions": list(PermissionCodes.catalog())}

    def api_encode_yaml(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return self._call(lambda: self._encode(body))

    def api_decode_yaml(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return self._call(lambda: self._decode(body))

    def _encode(self, body: Dict[str, Any]) -> Dict[str, Any]:
        document = body.get("document", body)
        if not isinstance(document, dict):
            raise OperatorError(
                "RBAC encode requires a document mapping.\n"
                "Fix: POST {document: {...}}",
                has_fix=False,
            )
        return self._writer.encode_yaml(document)

    def _decode(self, body: Dict[str, Any]) -> Dict[str, Any]:
        yaml_text = body.get("yaml")
        if not isinstance(yaml_text, str):
            raise OperatorError(
                "RBAC decode requires yaml text.\nFix: POST {yaml: \"...\"}",
                has_fix=False,
            )
        return self._writer.decode_yaml(yaml_text)

    @staticmethod
    def _call(action):
        try:
            return action()
        except OperatorError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
