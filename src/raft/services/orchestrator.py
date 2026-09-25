"""High-level up / down / sync / redeploy / gate recreate orchestration."""

from __future__ import annotations

import logging
from typing import Optional

from raft.errors import OperatorError, append_diagnostics

from ..adapters.docker import DockerStack
from ..adapters.http import HttpProbe
from ..adapters.nginx import NginxUpstreams
from ..adapters.shell import Shell
from ..config.settings import load_config
from ..models.stack import Stack
from ..ui import say
from .certs import require_origin_certs
from .cutover import DEPLOY_CUTOVER, CutoverSession, wait_until
from .readiness import ReadinessStrategy
from .render import (
    StackRenderer,
    fingerprint_gate_nginx,
    read_gate_nginx_reload_stamp,
    write_gate_nginx_reload_stamp,
)
from .sync import SourceSync

logger = logging.getLogger(__name__)


class Orchestrator:
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
        apps = [self.stack.app(n) for n in names] if names else list(self.stack.apps)
        for app in apps:
            self.nginx.ensure_steady_file(app)
        self.syncer.sync(apps, ref_override=ref_override, force=force)
        self.render()

    def render(self) -> None:
        StackRenderer(self.stack).render()
        disk = fingerprint_gate_nginx(self.stack.root)
        if self.stack.gate in self.docker.running_services():
            loaded = read_gate_nginx_reload_stamp(self.stack.root)
            if loaded != disk:
                # Fail before nginx -t so operators see doctor-style PEM guidance.
                require_origin_certs(self.stack)
                self.docker.reload_gate_nginx()
                write_gate_nginx_reload_stamp(self.stack.root, disk)
                say("reloaded gate nginx (edge TLS/http/stream config)", style="info")
        say("rendered generated/ from applied App manifests + edge settings", style="ok")

    def _mark_gate_nginx_loaded(self) -> None:
        """Gate process just started/recreated with current on-disk fragments."""
        write_gate_nginx_reload_stamp(
            self.stack.root, fingerprint_gate_nginx(self.stack.root)
        )

    def _wait_app_ready(self, app, *, timeout: Optional[float] = None) -> None:
        spec = self.stack.spec_for(app)
        strategy = ReadinessStrategy.from_spec(spec)
        predicate = strategy.wait_predicate(
            app,
            self.stack,
            self.http,
            compose_ready=lambda: self.docker.service_is_ready(app.compose_id),
        )
        if predicate is None:
            return
        if strategy.kind == "http":
            label = f"Host {app.public_host}"
        elif strategy.port is not None and strategy.port.expose == "none":
            label = f"compose readiness for {app.name}"
        else:
            label = f"{strategy.kind} readiness for {app.name}"
        wait_budget = timeout if timeout is not None else strategy.timeout_seconds
        wait_until(
            label,
            predicate,
            timeout=wait_budget,
            interval=1.0,
            fix=(
                f"check readiness/health for {app.name}; raft doctor. "
                f"If Compose health stays 'starting'/'unhealthy', raise "
                f"readiness.timeoutSeconds in .raft/app.yaml "
                f"[{strategy.timing_summary()}]"
            ),
            diagnostics=lambda: self.docker.diagnostics_for(app.compose_id),
        )

    def start(self) -> None:
        running = self.docker.running_services()
        if running:
            joined = ", ".join(running)
            raise OperatorError(
                f"stack already running ({joined}). "
                "Refusing to rebuild/reload everything — "
                "run `raft down` first, "
                "or `raft redeploy <app|router>` for a targeted update.",
                has_fix=False,
            )
        logger.info("syncing service sources from inventory")
        self.sync()
        require_origin_certs(self.stack)
        logger.info("starting stack")
        self.docker.start_stack()
        self._assert_core_edge_running()
        self._mark_gate_nginx_loaded()
        logger.info("waiting for readiness checks")
        for app in self.stack.apps:
            self._wait_app_ready(app)
        say("stack is up", style="ok")
        say("redeploy with: raft redeploy <app>", style="info")

    def _assert_core_edge_running(self) -> None:
        """Compose can report Started even when nginx then exits on bad config."""
        expected = (self.stack.gate, self.stack.router)
        running = set(self.docker.running_services())
        missing = [name for name in expected if name not in running]
        if missing:
            message = (
                f"stack start incomplete — missing running services: {missing}.\n"
                f"Fix: docker compose -f ~/.raft/compose.yaml logs "
                f"{self.stack.gate} {self.stack.router}\n"
                f"     raft render && raft doctor"
            )
            raise OperatorError(
                append_diagnostics(
                    message,
                    self.docker.diagnostics_for(*missing),
                )
            )

    def stop(self) -> None:
        running = self.docker.running_services()
        if not running:
            say("stack already stopped", style="info")
            for app in self.stack.apps:
                self.docker.remove_container(app.tmp_container)
            return
        logger.info("stopping stack (%s)", ", ".join(running))
        self.docker.stop_stack()
        say("stack stopped", style="ok")

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
        edge = load_config(self.stack.root).edge
        for port, _protocol in edge.published_ports():
            wait_until(
                f"edge listener :{port}",
                lambda p=port: self.http.tcp_port_ok(p),
                timeout=30,
                interval=0.5,
            )
        say("gate recreated", style="ok")

    def redeploy_router(self) -> None:
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
        say("router redeployed", style="ok")

    def redeploy_app(
        self,
        app_name: str,
        *,
        ref_override: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
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

        try:
            for index, step in enumerate(DEPLOY_CUTOVER, start=1):
                logger.info("%s/%s %s", index, len(DEPLOY_CUTOVER), step.key)
                step.run(session)
        except Exception:
            logger.exception(
                "ERROR during redeploy of %s; running abort cleanup "
                "(restore stable upstream, remove tmp)",
                app.name,
            )
            try:
                session.abort_cleanup()
            except Exception:  # noqa: BLE001 — never mask the cutover error
                logger.warning(
                    "abort cleanup raised while handling redeploy failure for %s",
                    app.name,
                    exc_info=True,
                )
            raise
        say(f"redeployed {app.name}", style="ok")

    def ensure_app_deployed(
        self,
        app_name: str,
        *,
        ref_override: Optional[str] = None,
        force_sync: bool = False,
    ) -> None:
        """Deploy an applied app: cutover if running, start service if edge is up, else full up."""
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
            joined = ", ".join(running)
            raise OperatorError(
                f"stack already running ({joined}). "
                "Refusing to rebuild/reload everything — "
                "run `raft down` first, "
                "or `raft redeploy <app|router>` for a targeted update.",
                has_fix=False,
            )
        logger.info("stack not up; full start to deploy %s", app_name)
        self.sync([app_name], ref_override=ref_override, force=force_sync)
        others = [a.name for a in self.stack.apps if a.name != app_name]
        if others:
            self.sync(others, force=force_sync)
        require_origin_certs(self.stack)
        logger.info("starting stack")
        self.docker.start_stack()
        self._assert_core_edge_running()
        self._mark_gate_nginx_loaded()
        logger.info("waiting for readiness checks")
        for app in self.stack.apps:
            self._wait_app_ready(app)
        say("stack is up", style="ok")
        say(f"deployed {app_name}", style="ok")
