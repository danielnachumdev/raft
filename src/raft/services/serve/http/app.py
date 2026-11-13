"""FastAPI application factory for ``raft serve``."""


from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from raft.core.core.models.stack import Stack
from raft.core.observe.ops.actions import ServiceActions
from raft.core.observe.ops.logs import Logs
from raft.core.observe.ops.status import Status
from raft.services.serve.auth.require import require_read, require_write
from ..alerts import ServeAlertsApi
from ..auth import ServeAuthWire
from ..events import ServeEventsApi
from ..firewall import ServeFirewallApi
from ..github import ServeGithubApi
from ..inbox import ServeInboxApi
from ..notifications import ServeNotificationsApi
from ..rbac import ServeRbacApi
from ..settings import ServeSettingsApi
from ..update import ServeUpdateApi
from .downloads import ServeDownloads
from .page import ServePage
from .paths import ServePaths
from .security_middleware import SecurityHeadersMiddleware

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
        inbox: Optional[ServeInboxApi] = None,
        rbac: Optional[ServeRbacApi] = None,
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
        self._inbox = inbox
        self._rbac = rbac
        self._port = port

    def create(self) -> FastAPI:
        app = FastAPI(title="raft serve", docs_url=None, redoc_url=None)
        app.state.raft_home = self.stack.root
        page, apis = self._components()
        self._register_api(app, page, *apis)
        ServeAuthWire(self.stack).apply(app)
        app.mount(
            "/assets",
            StaticFiles(directory=str(ServePaths.spa_assets_dir())),
            name="assets",
        )
        self._register_spa(app, page)
        # Last added = outermost so auth denials also get security headers.
        app.add_middleware(SecurityHeadersMiddleware)
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
        return (
            self._downloads or ServeDownloads(self.stack, logs=self._logs),
            self._github or ServeGithubApi(self.stack, port=self._port),
            self._notifications or ServeNotificationsApi(self.stack),
            self._firewall or ServeFirewallApi(self.stack),
            self._alerts or ServeAlertsApi(self.stack),
            self._events or ServeEventsApi(self.stack),
            self._settings or ServeSettingsApi(self.stack),
            self._update or ServeUpdateApi(self.stack),
            self._inbox or ServeInboxApi(self.stack),
            self._rbac or ServeRbacApi(self.stack),
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
        inbox: ServeInboxApi,
        rbac: ServeRbacApi,
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
        inbox.register(app)
        rbac.register(app)

    @staticmethod
    def _register_read_api(app: FastAPI, page: ServePage) -> None:
        status_r = Depends(require_read("status"))
        metrics_r = Depends(require_read("metrics"))
        service_r = Depends(require_read("service"))
        logs_r = Depends(require_read("logs"))
        app.get("/api/status", dependencies=[status_r])(page.api_status)
        app.get("/api/metrics/http", dependencies=[metrics_r])(page.api_metrics_http)
        app.get("/api/metrics", dependencies=[metrics_r])(page.api_metrics)
        app.get("/api/service/{name}", dependencies=[service_r])(page.api_service)
        app.get("/api/service/{name}/http-requests", dependencies=[service_r])(
            page.api_service_http_requests
        )
        app.get("/api/service/{name}/definition", dependencies=[service_r])(
            page.api_service_definition
        )
        app.get("/api/service/{name}/logs/follow", dependencies=[logs_r])(
            page.api_service_logs_follow
        )
        app.get("/api/service/{name}/logs", dependencies=[logs_r])(
            page.api_service_logs
        )

    @staticmethod
    def _register_action_api(app: FastAPI, page: ServePage) -> None:
        runtime_w = Depends(require_write("runtime"))
        app.post("/api/service/{name}/up", dependencies=[runtime_w])(
            page.api_service_up
        )
        app.post("/api/service/{name}/down", dependencies=[runtime_w])(
            page.api_service_down
        )
        app.post("/api/service/{name}/redeploy", dependencies=[runtime_w])(
            page.api_service_redeploy
        )
        app.post("/api/purge", dependencies=[runtime_w])(page.api_purge)

    @staticmethod
    def _register_download_api(app: FastAPI, downloads: ServeDownloads) -> None:
        metrics_r = Depends(require_read("metrics"))
        logs_r = Depends(require_read("logs"))
        app.get("/api/exports", dependencies=[metrics_r])(
            downloads.api_export_catalog
        )
        app.get("/api/metrics/download", dependencies=[metrics_r])(
            downloads.api_metrics_download
        )
        app.get("/api/service/{name}/logs/download", dependencies=[logs_r])(
            downloads.api_logs_download
        )

    @staticmethod
    def _register_spa(app: FastAPI, page: ServePage) -> None:
        app.get("/")(page.index)
        app.get("/{full_path:path}")(page.index)
