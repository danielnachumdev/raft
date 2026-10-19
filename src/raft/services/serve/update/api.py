"""FastAPI handlers for Settings → Check for updates."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.update import SelfUpdate, UpdateCheck


class ServeUpdateApi:
    """Localhost JSON API over ``UpdateCheck`` + ``SelfUpdate``."""

    def __init__(
        self,
        stack: Stack,
        *,
        check: Optional[UpdateCheck] = None,
        updater: Optional[SelfUpdate] = None,
    ) -> None:
        self.stack = stack
        self._check = check or UpdateCheck()
        self._updater = updater or SelfUpdate(stack)

    def register(self, app) -> None:
        app.get("/api/update/status")(self.api_status)
        app.post("/api/update")(self.api_apply)

    def api_status(self) -> Dict[str, Any]:
        try:
            return self._check.status().as_public()
        except OperatorError as exc:
            raise self._bad(exc) from exc

    def api_apply(
        self, body: Optional[Dict[str, Any]] = Body(default=None)
    ) -> Dict[str, Any]:
        ref = self._optional_ref(body)
        try:
            outcome = self._updater.run(ref=ref, announce=False)
        except OperatorError as exc:
            raise self._bad(exc) from exc
        return outcome.as_public()

    @staticmethod
    def _optional_ref(body: Optional[Dict[str, Any]]) -> Optional[str]:
        if not body or not isinstance(body, dict):
            return None
        raw = body.get("ref")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
