"""HTTP handler dispatching activity/wake requests to a bound ``Scaler``."""

import logging
from http.server import BaseHTTPRequestHandler
from typing import ClassVar

from ..jobs.scale.scale import Scaler
from .path import WakeHttpPath

logger = logging.getLogger(__name__)


class WakeHttpHandler(BaseHTTPRequestHandler):
    """Dispatch activity/wake requests to a bound ``Scaler``."""

    scaler: Scaler
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
