"""High-level up / down / sync / redeploy / gate recreate orchestration."""

from __future__ import annotations

import logging
from typing import Optional

from raft.errors import (
    OperatorError,
    append_diagnostics,
    stack_already_running,
    stack_down_incomplete,
)

from ...adapters.docker import DockerStack
from ...adapters.http import HttpProbe
from ...adapters.nginx import NginxUpstreams
from ...adapters.shell import Shell
from ...config.settings import load_config
from ...models.graph_event_store import GraphEventStore
from ...models.scaling_store import ScalingStore
from ...models.stack import Stack
from ...ui import say
from ..ops.certs import require_origin_certs
from ..render import StackRenderer
from ..render.gate_nginx import GateNginxStamp
from ..sync import SourceSync
from .locking import stack_lock
from .orchestrator_deploy import OrchestratorDeploy
from .readiness import ReadinessStrategy
from .wait import wait_until

logger = logging.getLogger(__name__)


class Orchestrator(OrchestratorDeploy):
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.shell = Shell(stack.root)
        self.docker = DockerStack(stack, self.shell)
        self.nginx = NginxUpstreams(stack, self.docker)
        self.http = HttpProbe(stack)
        self.syncer = SourceSync(stack, self.shell)

    def sync(
        self,
        names: Optional[list[str]] = None,
        *,
        ref_override: Optional[str] = None,
        force: bool = False,
    ) -> None:
        with stack_lock(self.stack.root):
            apps = [self.stack.app(n) for n in names] if names else list(self.stack.apps)
            for app in apps:
                self.nginx.ensure_steady_file(app)
            self.syncer.sync(apps, ref_override=ref_override, force=force)
            self.render()

    def render(self) -> None:
        with stack_lock(self.stack.root):
            StackRenderer(self.stack).render()
            stamp = GateNginxStamp(self.stack.root)
            disk = stamp.fingerprint()
            if self.stack.gate in self.docker.running_services():
                if stamp.read() != disk:
                    # Fail before nginx -t so operators see doctor-style PEM guidance.
                    require_origin_certs(self.stack)
                    self.docker.reload_gate_nginx()
                    stamp.write(disk)
                    say("reloaded gate nginx (edge TLS/http/stream config)", style="info")
            say("rendered generated/ from applied App manifests + edge settings", style="ok")

    def _mark_gate_nginx_loaded(self) -> None:
        """Gate process just started/recreated with current on-disk fragments."""
        stamp = GateNginxStamp(self.stack.root)
        stamp.write(stamp.fingerprint())

    def _wait_app_ready(self, app, *, timeout: Optional[float] = None) -> None:
        if self._skip_scaled_host_wait(app):
            return
        strategy = ReadinessStrategy.from_spec(self.stack.spec_for(app))
        predicate = strategy.wait_predicate(
            app,
            self.stack,
            self.http,
            compose_ready=lambda: self.docker.service_is_ready(app.compose_id),
        )
        if predicate is None:
            return
        wait_until(
            self._readiness_label(app, strategy),
            predicate,
            timeout=timeout if timeout is not None else strategy.timeout_seconds,
            interval=1.0,
            fix=self._ready_fix(app, strategy),
            diagnostics=lambda: self.docker.diagnostics_for(app.compose_id),
        )

    def _skip_scaled_host_wait(self, app) -> bool:
        """Gate holds scaled apps; doctor skips Host too — don't fail `raft up` on 404."""
        if not app.public_host:
            return False
        if not ScalingStore(self.stack.root).is_scaled_to_zero(app.name):
            return False
        logger.info("skip Host readiness for %s (scaled to zero)", app.name)
        return True

    def _reload_router_for_host_waits(self) -> None:
        """Re-resolve upstream DNS after Compose start (router may have raced apps)."""
        logger.info("reloading router nginx before Host readiness waits")
        self.docker.reload_router_nginx()

    @staticmethod
    def _ready_fix(app, strategy) -> str:
        return (
            f"check readiness/health for {app.name}; raft doctor. "
            f"If Compose health stays 'starting'/'unhealthy', raise "
            f"readiness.timeoutSeconds in .raft/app.yaml "
            f"[{strategy.timing_summary()}]"
        )

    @staticmethod
    def _readiness_label(app, strategy) -> str:
        if strategy.kind == "http":
            path = strategy.path if strategy.path.startswith("/") else f"/{strategy.path}"
            return f"Host {app.public_host}{path}"
        if strategy.port is not None and strategy.port.expose == "none":
            return f"compose readiness for {app.name}"
        return f"{strategy.kind} readiness for {app.name}"

    def start(self) -> None:
        with stack_lock(self.stack.root):
            running = self.docker.running_services()
            if running:
                self._refuse_full_rebuild(running)
            logger.info("syncing service sources from inventory")
            self.sync()
            require_origin_certs(self.stack)
            self._bring_stack_up()
            GraphEventStore(self.stack.root).record_stack_up()
            say("stack is up", style="ok")
            say("redeploy with: raft redeploy <app>", style="info")

    def _refuse_full_rebuild(self, running: list[str]) -> None:
        raise stack_already_running(running, holders=self.docker.network_holders())

    def _assert_core_edge_running(self) -> None:
        """Compose can report Started even when nginx then exits on bad config."""
        expected = (self.stack.gate, self.stack.router, self.stack.controller)
        running = set(self.docker.running_services())
        missing = [name for name in expected if name not in running]
        if missing:
            message = (
                f"stack start incomplete — missing running services: {missing}.\n"
                f"Fix: docker compose -f ~/.raft/compose.yaml logs "
                f"{self.stack.gate} {self.stack.router} {self.stack.controller}\n"
                f"     raft render && raft doctor"
            )
            raise OperatorError(
                append_diagnostics(
                    message,
                    self.docker.diagnostics_for(*missing),
                )
            )

    def stop(self) -> None:
        with stack_lock(self.stack.root):
            running = self.docker.running_services()
            if not running:
                say("stack already stopped", style="info")
                for app in self.stack.apps:
                    self.docker.remove_container(app.tmp_container)
                self.docker.stop_stack()
                self._assert_stack_stopped()
                GraphEventStore(self.stack.root).record_stack_down()
                return
            logger.info("stopping stack (%s)", ", ".join(running))
            self.docker.stop_stack()
            self._assert_stack_stopped()
            GraphEventStore(self.stack.root).record_stack_down()
            say("stack stopped", style="ok")

    def _assert_stack_stopped(self) -> None:
        still = self.docker.running_services()
        holders = self.docker.network_holders()
        if still:
            raise stack_down_incomplete(still, holders=holders)
        if holders:
            say(
                "network still has containers after down: "
                + ", ".join(holders)
                + " — another process may have restarted the stack; "
                "run `raft down` again before `raft up`",
                style="warn",
            )

    def redeploy(self, target: str) -> None:
        # Accept short edge aliases (gate/router) or full compose ids.
        if target in ("router", self.stack.router):
            self.redeploy_router()
            return
        if target in ("gate", self.stack.gate):
            raise OperatorError(
                "refusing to redeploy `gate` — it is the stable public edge. "
                "To change published edge ports, run `raft gate recreate` "
                "(brief edge downtime).",
                has_fix=False,
            )
        self.redeploy_app(target)

    def recreate_gate(self) -> None:
        with stack_lock(self.stack.root):
            if self.stack.gate not in self.docker.running_services():
                raise OperatorError(
                    "gate is not running — bring the stack up first",
                    has_fix=False,
                )
            require_origin_certs(self.stack)
            self.render()
            say(
                "recreating gate to pick up published edge ports "
                "(brief edge downtime — typically 1–2s)",
                style="warn",
            )
            self.docker.recreate_gate()
            self._mark_gate_nginx_loaded()
            self._wait_edge_listeners()
            GraphEventStore(self.stack.root).record_gate_recreate()
            say("gate recreated", style="ok")

    def _wait_edge_listeners(self) -> None:
        edge = load_config(self.stack.root).edge
        for port, _protocol in edge.published_ports():
            wait_until(
                f"edge listener :{port}",
                lambda p=port: self.http.tcp_port_ok(p),
                timeout=30,
                interval=0.5,
            )

    def redeploy_router(self) -> None:
        with stack_lock(self.stack.root):
            if self.stack.gate not in self.docker.running_services():
                raise OperatorError(
                    "gate is not running — bring the stack up first",
                    has_fix=False,
                )
            logger.info("recreating inner router (gate stays up)")
            self.docker.recreate_router()
            logger.info("waiting for readiness via gate")
            for app in self.stack.apps:
                self._wait_app_ready(app)
            GraphEventStore(self.stack.root).record_deployment(
                service=self.stack.router,
                app="router",
                ref="-",
                label="Redeploy router",
            )
            say("router redeployed", style="ok")
