"""FastAPI handlers for ``host/rbac.yaml`` (#307)."""

from typing import Any, Dict, Optional

from fastapi import Body, Depends, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.rbac import PermissionCodes
from raft.core.core.rbac.document import RbacDocument
from raft.core.core.rbac.writer import RbacDocumentWriter
from raft.core.lifecycle.dashboard.oauth_refresh import OAuthAllowlistRefresh
from raft.core.lifecycle.dashboard.rbac_allowlist_sync import RbacAllowlistSync
from raft.services.serve.auth.require import require_read, require_write


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
        app.state.raft_home = self.stack.root
        app.get("/api/rbac", dependencies=[Depends(require_read("rbac"))])(
            self.api_get
        )
        app.put("/api/rbac", dependencies=[Depends(require_write("rbac"))])(
            self.api_put
        )
        app.get(
            "/api/rbac/catalog", dependencies=[Depends(require_read("rbac"))]
        )(self.api_catalog)
        app.post(
            "/api/rbac/yaml/encode",
            dependencies=[Depends(require_read("rbac"))],
        )(self.api_encode_yaml)
        app.post(
            "/api/rbac/yaml/decode",
            dependencies=[Depends(require_write("rbac"))],
        )(self.api_decode_yaml)

    def api_get(self) -> Dict[str, Any]:
        return self._writer.export_document()

    def api_put(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return self._call(lambda: self._replace_and_sync(body))

    def _replace_and_sync(self, body: Dict[str, Any]) -> Dict[str, Any]:
        result = self._writer.replace(body)
        document = RbacDocument.from_mapping(
            result.get("document") or {},
            path="host/rbac.yaml",
        )
        admission = RbacAllowlistSync(self.stack.root).sync(document)
        refresh = OAuthAllowlistRefresh(self.stack).after_sync(admission)
        result["admission"] = {**admission, "refresh": refresh}
        return result

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
