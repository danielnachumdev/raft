"""Edge exposure handlers — one per ``ports[].expose`` mode."""

from __future__ import annotations

from typing import Dict, Protocol

from ....config.settings_types import EdgeConfig
from ....models.app import App
from ....models.manifest import AppSpec
from ....models.ports import PortSpec
from .fragments import EdgeFragments
from .http import HttpEdge
from .modes import HostEdge, NoneEdge
from .stream import StreamEdge
from .tls import TlsEdge

__all__ = [
    "EDGE_HANDLERS",
    "EdgeFragments",
    "EdgeHandler",
    "EdgeHandlers",
    "HostEdge",
    "HttpEdge",
    "NoneEdge",
    "StreamEdge",
    "TlsEdge",
]


class EdgeHandler(Protocol):  # pragma: no cover
    def contribute(
        self,
        app: App,
        spec: AppSpec,
        port: PortSpec,
        *,
        edge: EdgeConfig,
    ) -> EdgeFragments: ...


EDGE_HANDLERS: Dict[str, EdgeHandler] = {
    "http": HttpEdge(),
    "stream": StreamEdge(),
    "host": HostEdge(),
    "none": NoneEdge(),
}


class EdgeHandlers:
    """Lookup table for ``ports[].expose`` → handler."""

    @staticmethod
    def for_expose(expose: str) -> EdgeHandler:
        try:
            return EDGE_HANDLERS[expose]
        except KeyError as exc:
            raise KeyError(f"no edge handler for expose={expose!r}") from exc
