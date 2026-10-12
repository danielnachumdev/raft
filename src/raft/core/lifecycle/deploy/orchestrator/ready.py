"""Host / compose readiness waits used by stack orchestrator."""

import logging
from typing import Optional

from raft.core.core.models.state.scaling_store import ScalingStore
from ..readiness import ReadinessStrategy
from ..wait import WaitUntil

logger = logging.getLogger(__name__)


class AppReadyWait:
    """Wait until an app's readiness strategy succeeds (or skip when scaled)."""

    def __init__(self, support) -> None:
        self._support = support

    def run(self, app, *, timeout: Optional[float] = None) -> None:
        if self._skip_scaled_host_wait(app):
            return
        strategy = ReadinessStrategy.from_spec(self._support.stack.spec_for(app))
        predicate = strategy.wait_predicate(
            app,
            self._support.stack,
            self._support.http,
            compose_ready=lambda: self._support.docker.service_is_ready(app.compose_id),
        )
        if predicate is None:
            return
        WaitUntil(
            self._label(app, strategy),
            predicate,
            timeout=timeout if timeout is not None else strategy.timeout_seconds,
            interval=1.0,
            fix=self._fix(app, strategy),
            diagnostics=lambda: self._support.docker.diagnostics_for(app.compose_id),
        ).run()

    def _skip_scaled_host_wait(self, app) -> bool:
        """Gate holds scaled apps; doctor skips Host too — don't fail ``raft up`` on 404."""
        if not app.public_host:
            return False
        if not ScalingStore(self._support.stack.root).is_scaled_to_zero(app.name):
            return False
        logger.info("skip Host readiness for %s (scaled to zero)", app.name)
        return True

    @staticmethod
    def _fix(app, strategy) -> str:
        return (
            f"check readiness/health for {app.name}; raft doctor. "
            f"If Compose health stays 'starting'/'unhealthy', raise "
            f"readiness.timeoutSeconds in .raft/app.yaml "
            f"[{strategy.timing_summary()}]"
        )

    @staticmethod
    def _label(app, strategy) -> str:
        if strategy.kind == "http":
            path = strategy.path if strategy.path.startswith("/") else f"/{strategy.path}"
            return f"Host {app.public_host}{path}"
        if strategy.port is not None and strategy.port.expose == "none":
            return f"compose readiness for {app.name}"
        return f"{strategy.kind} readiness for {app.name}"
