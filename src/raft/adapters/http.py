"""Public Host HTTP probes and TCP listener checks."""

import logging
import socket
import urllib.error
import urllib.request

from ..models.app import App
from ..models.stack import Stack

logger = logging.getLogger(__name__)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Keep the first response — oauth gates 302 off-box and break follow-based probes."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class HttpProbe:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self._opener = urllib.request.build_opener(_NoRedirect)

    def public_host_ok(self, app: App, *, path: str = "/") -> bool:
        if not app.public_host:
            return True
        request = urllib.request.Request(
            self._public_url(path),
            headers={"Host": app.public_host},
            method="GET",
        )
        try:
            with self._opener.open(request, timeout=3) as response:
                return self._accept_status(app.public_host, response.status)
        except urllib.error.HTTPError as exc:
            # No-redirect opener surfaces 3xx as HTTPError; treat as edge-reachable.
            return self._accept_status(app.public_host, exc.code, via="HTTPError")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            logger.debug("probe Host %s failed: %s", app.public_host, exc)
            return False

    def _public_url(self, path: str) -> str:
        suffix = path if path.startswith("/") else f"/{path}"
        return self.stack.public_base_url.rstrip("/") + suffix

    def _accept_status(self, host: str, status: int, *, via: str = "") -> bool:
        ok = self._status_ok(status)
        suffix = f" ({via})" if via else ""
        logger.debug("probe Host %s -> %s%s", host, status, suffix)
        return ok

    @staticmethod
    def _status_ok(status: int) -> bool:
        # 2xx/3xx: includes oauth login redirects and oauth2-proxy static 202.
        return 200 <= status < 400

    def tcp_port_ok(self, port: int, *, host: str = "127.0.0.1") -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                logger.debug("tcp probe %s:%s ok", host, port)
                return True
        except OSError as exc:
            logger.debug("tcp probe %s:%s failed: %s", host, port, exc)
            return False
