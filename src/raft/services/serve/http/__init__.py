"""FastAPI surface for ``raft serve`` (app factory, routes, SPA paths)."""

from .app import ServeAppFactory
from .downloads import ServeDownloads
from .instructions import ServeInstructions
from .log_stream import LogSseStream
from .page import ServePage
from .paths import ServePaths
from .security_middleware import SecurityHeadersMiddleware

__all__ = [
    "LogSseStream",
    "SecurityHeadersMiddleware",
    "ServeAppFactory",
    "ServeDownloads",
    "ServeInstructions",
    "ServePage",
    "ServePaths",
]
