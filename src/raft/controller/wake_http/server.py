"""Localhost/compose-network wake HTTP server for the gate."""

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Type

from ..jobs.scale.scale import Scaler
from .handler import WakeHttpHandler

logger = logging.getLogger(__name__)


class WakeHttpServer:
    """Bind localhost/compose-network wake API for the gate (not public)."""

    def __init__(
        self,
        scaler: Scaler,
        host: str = "0.0.0.0",
        port: int = 8090,
    ) -> None:
        self.scaler = scaler
        self.host = host
        self.port = port
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @classmethod
    def bind(
        cls,
        scaler: Scaler,
        host: str = "0.0.0.0",
        port: int = 8090,
    ) -> "WakeHttpServer":
        server = cls(scaler, host=host, port=port)
        server.start()
        return server

    def start(self) -> None:
        self._httpd = HTTPServer((self.host, self.port), self._handler_type())
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="raft-wake-http",
            daemon=True,
        )
        self._thread.start()
        logger.info("wake http listening on %s:%s", self.host, self.port)

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None

    def _handler_type(self) -> Type[BaseHTTPRequestHandler]:
        return type(
            "WakeHandlerBound",
            (WakeHttpHandler,),
            {"scaler": self.scaler},
        )
