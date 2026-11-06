"""FastAPI handlers for the in-app operator inbox (not outbound channels)."""

from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.inbox import OperatorInboxService
from raft.services.serve.auth.require import require_read, require_write


class ServeInboxApi:
    """Localhost JSON API over the derived operator inbox feed."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[OperatorInboxService] = None,
    ) -> None:
        self.stack = stack
        self._service = service or OperatorInboxService(stack.root)

    def register(self, app) -> None:
        app.state.raft_home = self.stack.root
        r, w = Depends(require_read("inbox")), Depends(require_write("inbox"))
        app.get("/api/inbox", dependencies=[r])(self.api_list)
        app.get("/api/inbox/summary", dependencies=[r])(self.api_summary)
        app.post("/api/inbox/mark-all-read", dependencies=[w])(self.api_mark_all_read)
        app.post("/api/inbox/items/{item_id}/read", dependencies=[w])(
            self.api_mark_read
        )
        app.post("/api/inbox/items/{item_id}/unread", dependencies=[w])(
            self.api_mark_unread
        )
        app.post("/api/inbox/items/{item_id}/dismiss", dependencies=[w])(
            self.api_dismiss
        )
        app.post("/api/inbox/read", dependencies=[w])(self.api_mark_read_many)
        app.post("/api/inbox/unread", dependencies=[w])(self.api_mark_unread_many)

    def api_list(self) -> Dict[str, Any]:
        return self._service.list_public()

    def api_summary(self) -> Dict[str, Any]:
        return self._service.summary()

    def api_mark_all_read(self) -> Dict[str, Any]:
        return self._service.mark_all_read()

    def api_mark_read(self, item_id: str) -> Dict[str, Any]:
        return self._service.mark_read([item_id])

    def api_mark_unread(self, item_id: str) -> Dict[str, Any]:
        return self._service.mark_unread([item_id])

    def api_dismiss(self, item_id: str) -> Dict[str, Any]:
        try:
            return self._service.dismiss(item_id)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_mark_read_many(
        self, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        return self._service.mark_read(self._ids(body))

    def api_mark_unread_many(
        self, body: Dict[str, Any] = Body(...)
    ) -> Dict[str, Any]:
        return self._service.mark_unread(self._ids(body))

    @staticmethod
    def _ids(body: Dict[str, Any]) -> List[str]:
        raw = body.get("ids")
        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="ids must be a list")
        return [str(item) for item in raw]

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
