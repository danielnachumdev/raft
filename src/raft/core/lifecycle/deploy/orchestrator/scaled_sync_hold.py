"""Hold scale-to-zero through sync/render so upstreams stay parked."""

import logging

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.scaling_store import ScalingStore

logger = logging.getLogger(__name__)


class ScaledSyncHold:
    """Park upstreams and clear scaledToZero only immediately before start."""

    def __init__(self, support) -> None:
        self._support = support

    def hold_for_sync(self, app) -> None:
        """Park upstreams and keep scaledToZero so sync/render cannot nginx -t steady DNS."""
        store = ScalingStore(self._support.stack.root)
        self._support.nginx.point_absent(app, reload=False)
        if store.is_scaled_to_zero(app.name):
            return
        store.mark_scaled_to_zero(app.name)
        logger.info("holding scaledToZero for %s through sync/render", app.name)

    def clear_before_start(self, app) -> None:
        """Mark awake after sync so readiness waits and compose start are not skipped."""
        store = ScalingStore(self._support.stack.root)
        if not store.is_scaled_to_zero(app.name):
            return
        store.mark_awake(app.name, min_up_seconds=self._min_up_seconds(app))
        logger.info("cleared scaledToZero for %s before single-generation start", app.name)

    def _min_up_seconds(self, app) -> float:
        try:
            scaling = self._support.stack.spec_for(app).scaling
        except OperatorError:
            return 60.0
        if scaling is None:
            return 60.0
        return float(scaling.min_up_seconds)
