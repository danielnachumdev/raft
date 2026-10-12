"""Cold ``compose up`` with scale-to-zero deferral."""

import logging
from typing import Optional, Sequence

from raft.core.lifecycle.acme.ensure import AcmeEnsure
from raft.core.lifecycle.acme.install import AcmeGateInstall
from ..up_scale_plan import StackUpScalePlan

logger = logging.getLogger(__name__)


class ColdStackUp:
    """Pull/mark deferred scale-to-zero apps; start the rest; wait ready; ACME."""

    def __init__(self, support) -> None:
        self._support = support

    def run(self) -> None:
        plan = StackUpScalePlan(self._support.stack)
        logger.info("starting stack")
        self._compose_up(plan)
        self._support._assert_core_edge_running()
        self._support._mark_gate_nginx_loaded()
        self._support._reload_router_for_host_waits()
        logger.info("waiting for readiness checks")
        for app in plan.apps_to_start():
            self._support._wait_app_ready(app)
        self.ensure_acme()

    def ensure_acme(self, app_names: Optional[Sequence[str]] = None) -> None:
        """Issue/renew ``tls: acme`` certs after gate is up; never fail deploy."""
        try:
            AcmeEnsure(
                self._support.stack,
                installer=AcmeGateInstall(self._support.stack, self._support.docker),
            ).run(app_names)
        except Exception as exc:  # noqa: BLE001 — apply/up must still succeed
            logger.warning("ACME ensure aborted (best-effort): %s", exc)

    def _compose_up(self, plan: StackUpScalePlan) -> None:
        if not plan.has_deferred():
            self._support.docker.start_stack()
            return
        self._prepare_deferred_images(plan)
        self._mark_and_park_deferred(plan)
        self._support.docker.start_stack(plan.start_compose_ids())

    def _mark_and_park_deferred(self, plan: StackUpScalePlan) -> None:
        """Mark deferred apps at zero and park upstreams before router starts."""
        plan.mark_scaled_to_zero()
        start_names = {app.name for app in plan.apps_to_start()}
        for app in self._support.stack.apps:
            if app.name not in start_names:
                self._support.nginx.point_absent(app, reload=False)

    def _prepare_deferred_images(self, plan: StackUpScalePlan) -> None:
        self._support.docker.pull_services(plan.deferred_pull_compose_ids())
        self._support.docker.build_services(plan.deferred_build_compose_ids())
