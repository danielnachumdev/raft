"""High-level up / down / sync / redeploy / gate recreate orchestration."""

import logging
from typing import Optional

from ...errors.cta import OperatorError
from ...errors.diagnostics import ServiceDiagnostics
from ...errors.domain import DomainErrors
from ...adapters.docker import DockerStack
from ...adapters.http import HttpProbe
from ...adapters.nginx import NginxUpstreams
from ...adapters.shell import Shell
from ...config.settings import SettingsLoader
from ...models.state.graph_event_store import GraphEventStore
from ...models.stack import Stack
from ...ui import OperatorSay
from ...ops.certs import CertProbe
from ...render.gate_nginx import GateNginxStamp
from ...render.stack_renderer import StackRenderer
from ...sync import SourceSync
from ...locking import StackLock
from ..wait import WaitUntil
from .deploy import OrchestratorDeploy
from .ready import AppReadyWait

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
        with StackLock(self.stack.root):
            apps = [self.stack.app(n) for n in names] if names else list(self.stack.apps)
            for app in apps:
                self.nginx.ensure_steady_file(app)
            self.syncer.sync(apps, ref_override=ref_override, force=force)
            self.render()

    def render(self) -> None:
        with StackLock(self.stack.root):
            StackRenderer(self.stack).render()
            stamp = GateNginxStamp(self.stack.root)
            disk = stamp.fingerprint()
            if self.stack.gate in self.docker.running_services():
                if stamp.read() != disk:
                    # Fail before nginx -t so operators see doctor-style PEM guidance.
                    CertProbe(self.stack).require_origin()
                    self.docker.reload_gate_nginx()
                    stamp.write(disk)
                    OperatorSay.say(
                        "reloaded gate nginx (edge TLS/http/stream config)", style="info"
                    )
            OperatorSay.say(
                "rendered generated/ from applied App manifests + edge settings",
                style="ok",
            )

    def _mark_gate_nginx_loaded(self) -> None:
        """Gate process just started/recreated with current on-disk fragments."""
        stamp = GateNginxStamp(self.stack.root)
        stamp.write(stamp.fingerprint())

    def _wait_app_ready(self, app, *, timeout: Optional[float] = None) -> None:
        AppReadyWait(self).run(app, timeout=timeout)

    def _reload_router_for_host_waits(self) -> None:
        """Re-resolve upstream DNS after Compose start (router may have raced apps)."""
        logger.info("reloading router nginx before Host readiness waits")
        self.docker.reload_router_nginx()

    def start(self) -> None:
        with StackLock(self.stack.root):
            running = self.docker.running_services()
            if running:
                self._refuse_full_rebuild(running)
            logger.info("syncing service sources from inventory")
            self.sync()
            CertProbe(self.stack).require_origin()
            self._bring_stack_up()
            GraphEventStore(self.stack.root).record_stack_up()
            OperatorSay.say("stack is up", style="ok")
            OperatorSay.say("redeploy with: raft redeploy <app>", style="info")

    def _refuse_full_rebuild(self, running: list) -> None:
        raise DomainErrors.stack_already_running(running, holders=self.docker.network_holders())

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
                ServiceDiagnostics.append_diagnostics(
                    message,
                    self.docker.diagnostics_for(*missing),
                )
            )

    def stop(self) -> None:
        with StackLock(self.stack.root):
            running = self.docker.running_services()
            if not running:
                OperatorSay.say("stack already stopped", style="info")
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
            OperatorSay.say("stack stopped", style="ok")

    def _assert_stack_stopped(self) -> None:
        still = self.docker.running_services()
        holders = self.docker.network_holders()
        if still:
            raise DomainErrors.stack_down_incomplete(still, holders=holders)
        if holders:
            OperatorSay.say(
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
        with StackLock(self.stack.root):
            if self.stack.gate not in self.docker.running_services():
                raise OperatorError(
                    "gate is not running — bring the stack up first",
                    has_fix=False,
                )
            CertProbe(self.stack).require_origin()
            self.render()
            OperatorSay.say(
                "recreating gate to pick up published edge ports "
                "(brief edge downtime — typically 1–2s)",
                style="warn",
            )
            self.docker.recreate_gate()
            self._mark_gate_nginx_loaded()
            self._wait_edge_listeners()
            GraphEventStore(self.stack.root).record_gate_recreate()
            OperatorSay.say("gate recreated", style="ok")

    def _wait_edge_listeners(self) -> None:
        edge = SettingsLoader().load(self.stack.root).edge
        for port, _protocol in edge.published_ports():
            WaitUntil(
                f"edge listener :{port}",
                lambda p=port: self.http.tcp_port_ok(p),
                timeout=30,
                interval=0.5,
            ).run()

    def redeploy_router(self) -> None:
        with StackLock(self.stack.root):
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
            OperatorSay.say("router redeployed", style="ok")
