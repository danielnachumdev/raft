"""Router nginx -t/reload with retry on Compose upstream DNS races."""

import logging
import time
from typing import Callable, Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.docker_msgs import DockerMessages
from ..shell import Shell

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], None]
ClockFn = Callable[[], float]


class RouterNginxReload:
    """Run ``nginx -t && reload``; retry while upstream Compose DNS is absent."""

    DEFAULT_TIMEOUT_SECONDS = 30.0
    DEFAULT_INTERVAL_SECONDS = 0.5

    def __init__(
        self,
        shell: Shell,
        router_service: str,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        interval: float = DEFAULT_INTERVAL_SECONDS,
        sleep: SleepFn = time.sleep,
        clock: ClockFn = time.monotonic,
    ) -> None:
        self._sh = shell
        self._router = router_service
        self._timeout = timeout
        self._interval = interval
        self._sleep = sleep
        self._clock = clock
        self._last_dns_error: Optional[OperatorError] = None

    def run(self) -> None:
        deadline = self._clock() + self._timeout
        while True:
            if self._attempt():
                return
            if self._clock() >= deadline:
                self._raise_timeout()
            self._sleep(self._interval)

    def _attempt(self) -> bool:
        try:
            self._test_and_reload()
            return True
        except OperatorError as exc:
            return self._retry_if_dns_race(exc)

    def _retry_if_dns_race(self, exc: OperatorError) -> bool:
        if not DockerMessages.looks_like_upstream_host_not_found(exc):
            raise exc
        self._last_dns_error = exc
        logger.info(
            "router nginx reload waiting for Compose DNS "
            "(host not found in upstream)"
        )
        return False

    def _test_and_reload(self) -> None:
        logger.info("nginx -t && reload on router")
        result = self._sh.compose(
            "exec", "-T", self._router, "nginx", "-t", capture=True, check=False
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise DockerMessages.nginx_rejected("router", detail)
        reload = self._sh.compose(
            "exec",
            "-T",
            self._router,
            "nginx",
            "-s",
            "reload",
            capture=True,
            check=False,
        )
        if reload.returncode != 0:
            detail = (reload.stderr or reload.stdout or "").strip()
            raise DockerMessages.nginx_reload_failed("router", detail)

    def _raise_timeout(self) -> None:
        if self._last_dns_error is not None:
            raise self._last_dns_error
        raise DockerMessages.nginx_rejected(
            "router",
            "timed out waiting for Compose DNS to resolve upstream hostnames",
        )
