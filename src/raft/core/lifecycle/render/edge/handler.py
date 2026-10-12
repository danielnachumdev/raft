"""Protocol for ``ports[].expose`` edge handlers."""

from typing import Protocol

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.ports import PortSpec
from .fragments import EdgeFragments


class EdgeHandler(Protocol):  # pragma: no cover
    def contribute(
        self,
        app: App,
        spec: AppSpec,
        port: PortSpec,
        *,
        edge: EdgeConfig,
    ) -> EdgeFragments: ...
