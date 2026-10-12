"""Lookup table for ``ports[].expose`` → edge handler."""

from .handler import EdgeHandler
from .strategies import HostEdge, HttpEdge, NoneEdge, StreamEdge

EDGE_HANDLERS: dict[str, EdgeHandler] = {
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
