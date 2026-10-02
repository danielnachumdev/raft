"""FastAPI application factory for ``raft serve``."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ...models import Stack
from ..ops.status import Status
from .page import ServePage
from .paths import ServePaths


class ServeAppFactory:
    """Build a localhost-only SPA + JSON status API over the stack."""

    def __init__(self, stack: Stack, status: Optional[Status] = None) -> None:
        self.stack = stack
        self._status = status

    def create(self) -> FastAPI:
        app = FastAPI(title="raft serve", docs_url=None, redoc_url=None)
        page = ServePage(self.stack, status=self._status)
        app.get("/api/status")(page.api_status)
        app.get("/api/metrics")(page.api_metrics)
        app.get("/")(page.index)
        app.mount(
            "/assets",
            StaticFiles(directory=str(ServePaths.spa_assets_dir())),
            name="assets",
        )
        return app
