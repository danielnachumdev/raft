"""Product Host / TCP readiness probes over HTTP and TCP gateways."""

import logging
from typing import Optional

from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from .gateway import HttpGateway
from .tcp import TcpGateway

logger = logging.getLogger(__name__)


class HttpProbe:
    """Stack-aware readiness checks (Host header + local TCP)."""

    def __init__(
        self,
        stack: Stack,
        *,
        http: Optional[HttpGateway] = None,
        tcp: Optional[TcpGateway] = None,
    ) -> None:
        self.stack = stack
        self._http = http or HttpGateway()
        self._tcp = tcp or TcpGateway()

    def public_host_ok(self, app: App, *, path: str = "/") -> bool:
        if not app.public_host:
            return True
        status = self._http.get(
            self._public_url(path),
            headers={"Host": app.public_host},
        )
        if status is None:
            logger.debug("probe Host %s failed: no response", app.public_host)
            return False
        return self._accept_status(app.public_host, status)

    def _public_url(self, path: str) -> str:
        suffix = path if path.startswith("/") else f"/{path}"
        return self.stack.public_base_url.rstrip("/") + suffix

    def _accept_status(self, host: str, status: int) -> bool:
        ok = self._status_ok(status)
        logger.debug("probe Host %s -> %s", host, status)
        return ok

    @staticmethod
    def _status_ok(status: int) -> bool:
        # 2xx/3xx: includes oauth login redirects and oauth2-proxy static 202.
        return 200 <= status < 400

    def tcp_port_ok(self, port: int, *, host: str = "127.0.0.1") -> bool:
        return self._tcp.connect(host, port)
