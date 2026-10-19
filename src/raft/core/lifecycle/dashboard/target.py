"""Synthetic App / AppSpec for first-party ``raft-dashboard`` edge + ACME."""

from typing import Optional

from raft.core.core.config.settings.dashboard_config import (
    DASHBOARD_SERVICE_NAME,
    DashboardConfig,
)
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.ports import PortSpec


class DashboardTarget:
    """Build synthetic inventory rows when dashboard has a public Host."""

    SERVICE_NAME = DASHBOARD_SERVICE_NAME

    def app(self, cfg: DashboardConfig) -> Optional[App]:
        if not cfg.enabled or not cfg.is_public():
            return None
        host = str(cfg.public_host).strip()
        return App(
            name=self.SERVICE_NAME,
            public_host=host,
            source="docker",
            path="",
            image="raft-dashboard",
        )

    def spec(self, cfg: DashboardConfig) -> AppSpec:
        return AppSpec(
            ports=(
                PortSpec(name="http", container_port=cfg.port, expose="http"),
            ),
            tls=cfg.tls if cfg.tls in {"off", "origin", "acme"} else "off",
            metadata_name=self.SERVICE_NAME,
        )

    def firewall_apps(self, cfg: DashboardConfig) -> list[App]:
        app = self.app(cfg)
        return [app] if app is not None else []
