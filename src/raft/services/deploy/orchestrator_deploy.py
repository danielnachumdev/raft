"""App deploy / cutover path for the stack orchestrator."""

from __future__ import annotations

import logging
from typing import Optional

from ...models.graph_event_store import GraphEventStore
from ...ui import say
from ..ops.certs import require_origin_certs
from .cutover import DEPLOY_CUTOVER, CutoverSession
from .locking import app_and_stack_locks
from .up_scale_plan import StackUpScalePlan

logger = logging.getLogger(__name__)


class OrchestratorDeploy:
    """Mixin: cutover redeploy and first-boot ensure_app_deployed."""

    def redeploy_app(
        self,
        app_name: str,
        *,
        ref_override: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
        with app_and_stack_locks(self.stack.root, app_name):
            app = self.stack.app(app_name)
            logger.info("syncing %s before cutover", app.name)
            self.sync([app.name], ref_override=ref_override, force=force_sync)
            session = CutoverSession(
                stack=self.stack,
                app=app,
                docker=self.docker,
                nginx=self.nginx,
                http=self.http,
            )
            logger.info("redeploy cutover for %s (%s)", app.name, app.public_host)
            self._run_cutover(session, app.name)
            self._record_deploy_event(app)
            say(f"redeployed {app.name}", style="ok")

    def _run_cutover(self, session: CutoverSession, app_name: str) -> None:
        try:
            for index, step in enumerate(DEPLOY_CUTOVER, start=1):
                logger.info("%s/%s %s", index, len(DEPLOY_CUTOVER), step.key)
                step.run(session)
        except Exception:
            logger.exception(
                "ERROR during redeploy of %s; running abort cleanup "
                "(restore stable upstream, remove tmp)",
                app_name,
            )
            self._safe_abort(session, app_name)
            raise

    @staticmethod
    def _safe_abort(session: CutoverSession, app_name: str) -> None:
        try:
            session.abort_cleanup()
        except Exception:  # noqa: BLE001 — never mask the cutover error
            logger.warning(
                "abort cleanup raised while handling redeploy failure for %s",
                app_name,
                exc_info=True,
            )

    def ensure_app_deployed(
        self,
        app_name: str,
        *,
        ref_override: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
        """Deploy an applied app: cutover if running, start service if edge is up, else full up."""
        with app_and_stack_locks(self.stack.root, app_name):
            app = self.stack.app(app_name)
            running = self.docker.running_services()
            if app.compose_id in running:
                self.redeploy_app(app_name, ref_override=ref_override, force_sync=force_sync)
                return
            if self.stack.gate in running:
                self._start_app_on_running_edge(
                    app, ref_override=ref_override, force_sync=force_sync
                )
                return
            self._start_stack_for_app(app_name, ref_override=ref_override, force_sync=force_sync)

    def _start_app_on_running_edge(
        self,
        app,
        *,
        ref_override: Optional[str],
        force_sync: bool,
    ) -> None:
        """Gate/router already up; sync, start this Compose service, reload router, wait ready."""
        logger.info("edge up; starting new app service %s", app.compose_id)
        self.sync([app.name], ref_override=ref_override, force=force_sync)
        self.docker.rebuild_service(app.compose_id)
        self.docker.nginx_test_and_reload()
        self._wait_app_ready(app)
        self._record_deploy_event(app)
        say(f"deployed {app.name}", style="ok")

    def _start_stack_for_app(
        self,
        app_name: str,
        *,
        ref_override: Optional[str],
        force_sync: bool,
    ) -> None:
        """Cold stack: sync (with this app's overrides) then bring everything up."""
        running = self.docker.running_services()
        if running:
            self._refuse_full_rebuild(running)
        logger.info("stack not up; full start to deploy %s", app_name)
        self._sync_cold_start(app_name, ref_override=ref_override, force_sync=force_sync)
        require_origin_certs(self.stack)
        self._bring_stack_up()
        GraphEventStore(self.stack.root).record_stack_up()
        self._record_deploy_event(self.stack.app(app_name))
        say("stack is up", style="ok")
        say(f"deployed {app_name}", style="ok")

    def _sync_cold_start(
        self, app_name: str, *, ref_override: Optional[str], force_sync: bool
    ) -> None:
        self.sync([app_name], ref_override=ref_override, force=force_sync)
        others = [a.name for a in self.stack.apps if a.name != app_name]
        if others:
            self.sync(others, force=force_sync)

    def _bring_stack_up(self) -> None:
        """Cold ``compose up``: pull/mark scale-to-zero apps; start the rest."""
        plan = StackUpScalePlan(self.stack)
        logger.info("starting stack")
        self._compose_up_with_scale_plan(plan)
        self._assert_core_edge_running()
        self._mark_gate_nginx_loaded()
        self._reload_router_for_host_waits()
        logger.info("waiting for readiness checks")
        for app in plan.apps_to_start():
            self._wait_app_ready(app)

    def _compose_up_with_scale_plan(self, plan: StackUpScalePlan) -> None:
        if not plan.has_deferred():
            self.docker.start_stack()
            return
        self._prepare_deferred_images(plan)
        self._mark_and_park_deferred(plan)
        self.docker.start_stack(plan.start_compose_ids())

    def _mark_and_park_deferred(self, plan: StackUpScalePlan) -> None:
        """Mark deferred apps at zero and park upstreams before router starts.

        Sync/render may still point upstreams at Compose DNS names while those
        services are intentionally not started (#92). Parking first avoids
        nginx ``host not found in upstream`` crash-loops on cold ``raft up``.
        """
        plan.mark_scaled_to_zero()
        start_names = {app.name for app in plan.apps_to_start()}
        for app in self.stack.apps:
            if app.name not in start_names:
                self.nginx.point_absent(app, reload=False)

    def _prepare_deferred_images(self, plan: StackUpScalePlan) -> None:
        services = plan.deferred_compose_ids()
        self.docker.pull_services(services)
        self.docker.build_services(services)

    def _record_deploy_event(self, app) -> None:
        """Append a GraphEvent so Trends charts can mark this deploy."""
        GraphEventStore(self.stack.root).record_deployment(
            service=app.compose_id,
            app=app.name,
            ref=app.ref,
        )
