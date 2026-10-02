"""FastAPI application factory for ``raft serve``."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ...models import Stack
from ..ops.status import Status
from .page import ServePage
from .paths import ServePaths


class ServeAppFactory:
    """Build a localhost-only shell + JSON status API over the stack."""

    def __init__(self, stack: Stack, status: Optional[Status] = None) -> None:
        self.stack = stack
        self._status = status

    def create(self) -> FastAPI:
        app = FastAPI(title="raft serve", docs_url=None, redoc_url=None)
        templates = Jinja2Templates(directory=str(ServePaths.templates_dir()))
        page = ServePage(self.stack, templates, status=self._status)
        app.get("/")(page.index)
        app.get("/api/status")(page.api_status)
        app.mount(
            "/static",
            StaticFiles(directory=str(ServePaths.static_dir())),
            name="static",
        )
        return app
