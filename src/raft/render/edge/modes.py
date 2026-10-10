"""Host-publish and internal-only edge handlers."""

from __future__ import annotations

from dataclasses import dataclass

from raft.config.settings_types import EdgeConfig
from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from .fragments import EdgeFragments


@dataclass(frozen=True)
class HostEdge:
    def contribute(
        self,
        app: App,
        spec: AppSpec,
        port: PortSpec,
        *,
        edge: EdgeConfig,
    ) -> EdgeFragments:
        public = port.public_port
        assert public is not None
        proto = "" if port.protocol == "tcp" else f"/{port.protocol}"
        return EdgeFragments(
            host_publish=[f'"{public}:{port.container_port}{proto}"'],
            expose_ports=[port.container_port],
        )


@dataclass(frozen=True)
class NoneEdge:
    """Internal-only port: Compose expose, no host publish, no router/gate."""

    def contribute(
        self,
        app: App,
        spec: AppSpec,
        port: PortSpec,
        *,
        edge: EdgeConfig,
    ) -> EdgeFragments:
        return EdgeFragments(expose_ports=[port.container_port])
