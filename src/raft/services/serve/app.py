"""FastAPI application factory for ``raft serve``."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ...models.stack import Stack
from ..ops.logs import Logs
from ..ops.status import Status
from .actions import ServeActions
from .downloads import ServeDownloads
from .github import ServeGithubApi
from .page import ServePage
from .paths import ServePaths

_DEFAULT_PORT = 8787


class ServeAppFactory:
    """Build a localhost-only SPA + JSON status API over the stack."""

    def __init__(
        self,
        stack: Stack,
        status: Optional[Status] = None,
        actions: Optional[ServeActions] = None,
        logs: Optional[Logs] = None,
        downloads: Optional[ServeDownloads] = None,
        github: Optional[ServeGithubApi] = None,
        port: int = _DEFAULT_PORT,
    ) -> None:
        self.stack = stack
        self._status = status
        self._actions = actions
        self._logs = logs
        self._downloads = downloads
        self._github = github
        self._port = port

    def create(self) -> FastAPI:
        app = FastAPI(title="raft serve", docs_url=None, redoc_url=None)
        page = ServePage(
            self.stack,
            status=self._status,
            actions=self._actions,
            logs=self._logs,
        )
        downloads = self._downloads or ServeDownloads(self.stack, logs=self._logs)
        github = self._github or ServeGithubApi(self.stack, port=self._port)
        self._register_api(app, page, downloads, github)
        app.mount(
            "/assets",
            StaticFiles(directory=str(ServePaths.spa_assets_dir())),
            name="assets",
        )
        self._register_spa(app, page)
        return app

    @staticmethod
    def _register_api(
        app: FastAPI,
        page: ServePage,
        downloads: ServeDownloads,
        github: ServeGithubApi,
    ) -> None:
        ServeAppFactory._register_read_api(app, page)
        ServeAppFactory._register_action_api(app, page)
        ServeAppFactory._register_download_api(app, downloads)
        github.register(app)

    @staticmethod
    def _register_read_api(app: FastAPI, page: ServePage) -> None:
        app.get("/api/status")(page.api_status)
        app.get("/api/metrics/http")(page.api_metrics_http)
        app.get("/api/metrics")(page.api_metrics)
        app.get("/api/service/{name}")(page.api_service)
        app.get("/api/service/{name}/logs/follow")(page.api_service_logs_follow)
        app.get("/api/service/{name}/logs")(page.api_service_logs)

    @staticmethod
    def _register_action_api(app: FastAPI, page: ServePage) -> None:
        app.post("/api/service/{name}/start")(page.api_service_start)
        app.post("/api/service/{name}/stop")(page.api_service_stop)
        app.post("/api/service/{name}/redeploy")(page.api_service_redeploy)

    @staticmethod
    def _register_download_api(app: FastAPI, downloads: ServeDownloads) -> None:
        app.get("/api/exports")(downloads.api_export_catalog)
        app.get("/api/metrics/download")(downloads.api_metrics_download)
        app.get("/api/service/{name}/logs/download")(downloads.api_logs_download)

    @staticmethod
    def _register_spa(app: FastAPI, page: ServePage) -> None:
        app.get("/")(page.index)
        app.get("/{full_path:path}")(page.index)
