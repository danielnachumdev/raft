"""Protocol for ``ports[].expose`` edge handlers."""

from typing import Protocol

from ...config.settings.types import EdgeConfig
from ...models.app import App
from ...models.manifest import AppSpec
from ...models.ports import PortSpec
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
