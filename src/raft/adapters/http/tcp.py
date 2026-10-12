"""Raw TCP connect probe."""

import logging
import socket

logger = logging.getLogger(__name__)


class TcpGateway:
    """Transport-level TCP connect check."""

    def connect(
        self,
        host: str,
        port: int,
        *,
        timeout: float = 0.4,
    ) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                logger.debug("tcp %s:%s ok", host, port)
                return True
        except OSError as exc:
            logger.debug("tcp %s:%s failed: %s", host, port, exc)
            return False
