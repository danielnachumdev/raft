"""App deploy / cutover path for the stack orchestrator."""

import logging
from typing import Optional, Sequence

from raft.core.core.errors.cta import OperatorError
from raft.core.core.errors.domain import DomainErrors
from raft.core.core.models.deployment_spec import DEFAULT_DEPLOYMENT_METHOD
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.core.ui import OperatorSay
from raft.core.observe.ops.certs import CertProbe
from raft.core.platform.locking import AppAndStackLocks
from ..dual_run import DualRunCutover
from ..methods.catalogs import DeploymentMethodCatalogs
from ..methods.method import DeploymentContext, DeploymentMethod
from .scaled_sync_hold import ScaledSyncHold
from .stack_up import ColdStackUp

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
        with AppAndStackLocks(self.stack.root, app_name):
            app = self.stack.app(app_name)
            running = self.docker.running_services()
            method = self._deployment_method(app)
            ctx = self._deploy_ctx(
                app, ref_override=ref_override, force_sync=force_sync, done="redeployed"
            )
            if DualRunCutover(self.stack.root).needed(app, running):
                method.deploy_when_up(ctx)
                return
            method.deploy_when_down(ctx)

    def ensure_app_deployed(
        self,
        app_name: str,
        *,
        ref_override: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
        """Deploy: method when live/edge-up; else full stack up."""
        with AppAndStackLocks(self.stack.root, app_name):
            app = self.stack.app(app_name)
            running = self.docker.running_services()
            method = self._deployment_method(app)
            ctx = self._deploy_ctx(
                app, ref_override=ref_override, force_sync=force_sync, done="deployed"
            )
            if DualRunCutover(self.stack.root).needed(app, running):
                method.deploy_when_up(ctx)
                return
            if self.stack.gate in running:
                method.deploy_when_down(ctx)
                return
            self._start_stack_for_app(app_name, ref_override=ref_override, force_sync=force_sync)

    def deploy_single_generation(
        self,
        app,
        *,
        ref_override: Optional[str],
        force_sync: bool,
        done: str = "deployed",
    ) -> None:
        """Idle / not running: one Compose start + readiness (no ``*_tmp``)."""
        if self.stack.gate not in self.docker.running_services():
            raise DomainErrors.service_not_running(app.compose_id)
        logger.info("no live replica for %s; skip *_tmp cutover", app.name)
        self._start_app_on_running_edge(
            app, ref_override=ref_override, force_sync=force_sync, done=done
        )

    def finish_app_deploy(self, app, *, done: str) -> None:
        """Record GraphEvent, best-effort ACME, and operator OK line."""
        self._record_deploy_event(app, done=done)
        self._ensure_acme_best_effort([app.name])
        OperatorSay.say(f"{done} {app.name}", style="ok")

    def _deployment_method(self, app) -> DeploymentMethod:
        method_id = self._method_id(app)
        return DeploymentMethodCatalogs.default().get(method_id)

    def _method_id(self, app) -> str:
        try:
            return self.stack.spec_for(app).deployment.method
        except OperatorError:
            return DEFAULT_DEPLOYMENT_METHOD

    def _deploy_ctx(
        self,
        app,
        *,
        ref_override: Optional[str],
        force_sync: bool,
        done: str,
    ) -> DeploymentContext:
        return DeploymentContext(
            support=self,
            app=app,
            ref_override=ref_override,
            force_sync=force_sync,
            done=done,
        )

    def _start_app_on_running_edge(
        self,
        app,
        *,
        ref_override: Optional[str],
        force_sync: bool,
        done: str = "deployed",
    ) -> None:
        """Gate/router already up; sync, start this Compose service, reload router, wait ready."""
        # Hold scaledToZero through sync/render so upstreams stay parked. Clearing
        # first made render write Compose DNS and router nginx -t fail before start
        # (nachum-mealie CD host-not-found). Also covers a prior failed wake that
        # left awake + steady DNS with no container.
        hold = ScaledSyncHold(self)
        hold.hold_for_sync(app)
        logger.info("edge up; starting new app service %s", app.compose_id)
        self.sync([app.name], ref_override=ref_override, force=force_sync)
        hold.clear_before_start(app)
        self.nginx.point_absent(app, reload=False)
        self._start_compose_generation(app, ref_override=ref_override)
        self.nginx.point_steady(app, reload=False)
        self.docker.nginx_test_and_reload()
        self._wait_app_ready(app)
        self.finish_app_deploy(app, done=done)

    def _start_compose_generation(self, app, *, ref_override: Optional[str]) -> None:
        """Pull+recreate docker-source pins; rebuild git/local checkouts."""
        if app.source == "docker":
            pull_ref = app.image_ref(self._wanted_image_tag(app, ref_override=ref_override))
            self.docker.recreate_pulled_service(app, pull_ref=pull_ref)
            return
        self.docker.rebuild_service(app.compose_id)

    def _wanted_image_tag(self, app, *, ref_override: Optional[str]) -> str:
        if ref_override:
            return ref_override
        state = self.stack.ref_state_file(app)
        try:
            lines = state.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return app.ref
        for line in lines:
            if line.startswith("# requested:"):
                parsed = line.split(":", 1)[1].strip()
                return parsed or app.ref
        return app.ref

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
        CertProbe(self.stack).require_origin()
        self._bring_stack_up()
        GraphEventStore(self.stack.root).record_stack_up()
        self._record_deploy_event(self.stack.app(app_name))
        OperatorSay.say("stack is up", style="ok")
        OperatorSay.say(f"deployed {app_name}", style="ok")

    def _sync_cold_start(
        self, app_name: str, *, ref_override: Optional[str], force_sync: bool
    ) -> None:
        self.sync([app_name], ref_override=ref_override, force=force_sync)
        others = [a.name for a in self.stack.apps if a.name != app_name]
        if others:
            self.sync(others, force=force_sync)

    def _bring_stack_up(self, *, build: bool = False) -> None:
        """Cold ``compose up``: pull/mark scale-to-zero apps; start the rest."""
        ColdStackUp(self).run(build=build)

    def _ensure_acme_best_effort(self, app_names: Optional[Sequence[str]] = None) -> None:
        ColdStackUp(self).ensure_acme(app_names)

    def _record_deploy_event(self, app, *, done: str = "deployed") -> None:
        """Append GraphEvent (+ ops dual-write) for apply / redeploy success."""
        action = "redeploy" if done == "redeployed" else "apply"
        GraphEventStore(self.stack.root).record_deployment(
            service=app.compose_id,
            app=app.name,
            ref=app.ref,
            action=action,
        )
