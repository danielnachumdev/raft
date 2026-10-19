"""FastAPI handlers for full ``settings.yaml`` GET/PUT."""

from typing import Any, Dict, Optional

from fastapi import Body, HTTPException

from raft.core.core.config.settings import OperatorSettingsService
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack


class ServeSettingsApi:
    """Localhost JSON API over the operator settings document."""

    def __init__(
        self,
        stack: Stack,
        *,
        service: Optional[OperatorSettingsService] = None,
    ) -> None:
        self.stack = stack
        self._service = service or OperatorSettingsService(stack.root)

    def register(self, app) -> None:
        app.get("/api/settings")(self.api_get)
        app.put("/api/settings")(self.api_put)

    def api_get(self) -> Dict[str, Any]:
        return self._service.get_public()

    def api_put(self, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            return self._service.replace(body)
        except OperatorError as exc:
            raise self._bad(exc) from exc

    @staticmethod
    def _bad(exc: OperatorError) -> HTTPException:
        return HTTPException(status_code=400, detail=str(exc))
