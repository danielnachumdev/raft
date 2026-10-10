"""Internal gate→controller HTTP for activity bumps and wake requests."""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, ClassVar, Optional, Tuple, Type
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .jobs import Scaler

__all__ = ["WakeHttpPath", "WakeHttpServer"]

logger = logging.getLogger(__name__)


class WakeHttpPath:
    """Parse ``/activity|wake/<name>`` request paths."""

    _ACTIONS = frozenset({"activity", "wake"})

    def parse(self, path: str) -> Tuple[Optional[str], Optional[str]]:
        parts = [p for p in urlparse(path).path.split("/") if p]
        if len(parts) != 2:
            return None, None
        action, name = parts[0], parts[1]
        if action not in self._ACTIONS:
            return None, None
        return action, name


class _WakeHttpHandler(BaseHTTPRequestHandler):
    """Dispatch activity/wake requests to a bound ``Scaler``."""

    scaler: "Scaler"
    _paths: ClassVar[WakeHttpPath] = WakeHttpPath()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        logger.debug("wake-http " + fmt, *args)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        action, name = self._paths.parse(self.path)
        if action is None or not name:
            self.send_error(404)
            return
        if action == "activity":
            self.scaler.record_activity(name)
            self._ok(204)
            return
        self.scaler.request_wake(name)
        self._ok(202)

    def _ok(self, code: int) -> None:
        self.send_response(code)
        self.end_headers()


class WakeHttpServer:
    """Bind localhost/compose-network wake API for the gate (not public)."""

    def __init__(
        self,
        scaler: "Scaler",
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
        scaler: "Scaler",
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
            (_WakeHttpHandler,),
            {"scaler": self.scaler},
        )
