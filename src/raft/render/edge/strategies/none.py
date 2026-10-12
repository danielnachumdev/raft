"""Internal-only edge handler (``expose: none``)."""

from dataclasses import dataclass

from ....config.settings.types import EdgeConfig
from ....models.app import App
from ....models.manifest import AppSpec
from ....models.ports import PortSpec
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
