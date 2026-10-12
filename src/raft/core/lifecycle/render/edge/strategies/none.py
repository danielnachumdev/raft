"""Internal-only edge handler (``expose: none``)."""

from dataclasses import dataclass

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.ports import PortSpec
from ..fragments import EdgeFragments


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
