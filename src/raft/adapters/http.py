"""Public Host HTTP probes and TCP listener checks."""

import logging
import socket
import urllib.error
import urllib.request

from ..models.app import App
from ..models.stack import Stack

logger = logging.getLogger(__name__)


class HttpProbe:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def public_host_ok(self, app: App) -> bool:
        if not app.public_host:
            return True
        request = urllib.request.Request(
            self.stack.public_base_url + "/",
            headers={"Host": app.public_host},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                ok = 200 <= response.status < 400
                logger.debug("probe Host %s -> %s", app.public_host, response.status)
                return ok
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            logger.debug("probe Host %s failed: %s", app.public_host, exc)
            return False

    def tcp_port_ok(self, port: int, *, host: str = "127.0.0.1") -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                logger.debug("tcp probe %s:%s ok", host, port)
                return True
        except OSError as exc:
            logger.debug("tcp probe %s:%s failed: %s", host, port, exc)
            return False
