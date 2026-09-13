"""Public Host HTTP probes."""

import logging
import urllib.error
import urllib.request

from ..models.inventory import App, Stack

logger = logging.getLogger(__name__)


class HttpProbe:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def public_host_ok(self, app: App) -> bool:
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
