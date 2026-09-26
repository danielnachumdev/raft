"""Internal gate→controller HTTP for activity bumps and wake requests."""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import TYPE_CHECKING, Optional, Tuple
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .scale import Scaler

__all__ = ["WakeHttpServer", "start_wake_http"]

logger = logging.getLogger(__name__)


class WakeHttpServer:
    """Bind localhost/compose-network wake API for the gate (not public)."""

    def __init__(self, scaler: "Scaler", host: str = "0.0.0.0", port: int = 8090) -> None:
        self.scaler = scaler
        self.host = host
        self.port = port
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        handler = _handler_for(self.scaler)
        self._httpd = HTTPServer((self.host, self.port), handler)
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


def start_wake_http(scaler: "Scaler", host: str = "0.0.0.0", port: int = 8090) -> WakeHttpServer:
    server = WakeHttpServer(scaler, host=host, port=port)
    server.start()
    return server


class _WakeHandler(BaseHTTPRequestHandler):
    scaler: "Scaler"

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        logger.debug("wake-http " + fmt, *args)

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def _dispatch(self) -> None:
        action, name = _parse_path(self.path)
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


def _handler_for(scaler: "Scaler") -> type:
    return type("WakeHandlerBound", (_WakeHandler,), {"scaler": scaler})


def _parse_path(path: str) -> Tuple[Optional[str], Optional[str]]:
    parsed = urlparse(path)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 2:
        return None, None
    action, name = parts[0], parts[1]
    if action not in {"activity", "wake"}:
        return None, None
    return action, name
