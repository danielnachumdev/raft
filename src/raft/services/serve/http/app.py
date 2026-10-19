"""FastAPI application factory for ``raft serve``."""


from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from raft.core.core.models.stack import Stack
from raft.core.observe.ops.actions import ServiceActions
from raft.core.observe.ops.logs import Logs
from raft.core.observe.ops.status import Status
from ..alerts import ServeAlertsApi
from ..auth import ServeAuthWire
from ..events import ServeEventsApi
from ..firewall import ServeFirewallApi
from ..github import ServeGithubApi
from ..notifications import ServeNotificationsApi
from ..settings import ServeSettingsApi
from ..update import ServeUpdateApi
from .downloads import ServeDownloads
from .page import ServePage
from .paths import ServePaths

_DEFAULT_PORT = 8787


class ServeAppFactory:
    """Build a localhost-only SPA + JSON status API over the stack."""

    def __init__(
        self,
        stack: Stack,
        status: Optional[Status] = None,
        actions: Optional[ServiceActions] = None,
        logs: Optional[Logs] = None,
        downloads: Optional[ServeDownloads] = None,
        github: Optional[ServeGithubApi] = None,
        notifications: Optional[ServeNotificationsApi] = None,
        firewall: Optional[ServeFirewallApi] = None,
        alerts: Optional[ServeAlertsApi] = None,
        events: Optional[ServeEventsApi] = None,
        settings: Optional[ServeSettingsApi] = None,
        update: Optional[ServeUpdateApi] = None,
        port: int = _DEFAULT_PORT,
    ) -> None:
        self.stack = stack
        self._status = status
        self._actions = actions
        self._logs = logs
        self._downloads = downloads
        self._github = github
        self._notifications = notifications
        self._firewall = firewall
        self._alerts = alerts
        self._events = events
        self._settings = settings
        self._update = update
        self._port = port

    def create(self) -> FastAPI:
        app = FastAPI(title="raft serve", docs_url=None, redoc_url=None)
        page, apis = self._components()
        self._register_api(app, page, *apis)
        ServeAuthWire(self.stack).apply(app)
        app.mount(
            "/assets",
            StaticFiles(directory=str(ServePaths.spa_assets_dir())),
            name="assets",
        )
        self._register_spa(app, page)
        return app

    def _components(self):
        page = ServePage(
            self.stack,
            status=self._status,
            actions=self._actions,
            logs=self._logs,
        )
        return page, self._api_adapters()

    def _api_adapters(self):
        downloads = self._downloads or ServeDownloads(self.stack, logs=self._logs)
        github = self._github or ServeGithubApi(self.stack, port=self._port)
        notifications = self._notifications or ServeNotificationsApi(self.stack)
        firewall = self._firewall or ServeFirewallApi(self.stack)
        alerts = self._alerts or ServeAlertsApi(self.stack)
        events = self._events or ServeEventsApi(self.stack)
        settings = self._settings or ServeSettingsApi(self.stack)
        update = self._update or ServeUpdateApi(self.stack)
        return (
            downloads,
            github,
            notifications,
            firewall,
            alerts,
            events,
            settings,
            update,
        )

    @staticmethod
    def _register_api(
        app: FastAPI,
        page: ServePage,
        downloads: ServeDownloads,
        github: ServeGithubApi,
        notifications: ServeNotificationsApi,
        firewall: ServeFirewallApi,
        alerts: ServeAlertsApi,
        events: ServeEventsApi,
        settings: ServeSettingsApi,
        update: ServeUpdateApi,
    ) -> None:
        ServeAppFactory._register_read_api(app, page)
        ServeAppFactory._register_action_api(app, page)
        ServeAppFactory._register_download_api(app, downloads)
        github.register(app)
        notifications.register(app)
        firewall.register(app)
        alerts.register(app)
        events.register(app)
        settings.register(app)
        update.register(app)

    @staticmethod
    def _register_read_api(app: FastAPI, page: ServePage) -> None:
        app.get("/api/status")(page.api_status)
        app.get("/api/metrics/http")(page.api_metrics_http)
        app.get("/api/metrics")(page.api_metrics)
        app.get("/api/service/{name}")(page.api_service)
        app.get("/api/service/{name}/http-requests")(page.api_service_http_requests)
        app.get("/api/service/{name}/logs/follow")(page.api_service_logs_follow)
        app.get("/api/service/{name}/logs")(page.api_service_logs)

    @staticmethod
    def _register_action_api(app: FastAPI, page: ServePage) -> None:
        app.post("/api/service/{name}/start")(page.api_service_start)
        app.post("/api/service/{name}/stop")(page.api_service_stop)
        app.post("/api/service/{name}/redeploy")(page.api_service_redeploy)
        app.post("/api/purge")(page.api_purge)

    @staticmethod
    def _register_download_api(app: FastAPI, downloads: ServeDownloads) -> None:
        app.get("/api/exports")(downloads.api_export_catalog)
        app.get("/api/metrics/download")(downloads.api_metrics_download)
        app.get("/api/service/{name}/logs/download")(downloads.api_logs_download)

    @staticmethod
    def _register_spa(app: FastAPI, page: ServePage) -> None:
        app.get("/")(page.index)
        app.get("/{full_path:path}")(page.index)
