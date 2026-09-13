"""High-level up / down / sync / redeploy orchestration."""

from __future__ import annotations

import logging
from typing import Optional

from .cutover import DEPLOY_CUTOVER, CutoverSession, wait_until
from ..adapters.docker import DockerStack
from ..adapters.http import HttpProbe
from ..models.inventory import Stack
from ..adapters.nginx import NginxUpstreams
from ..adapters.shell import Shell
from .sync import SourceSync
from ..ui import say

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
        # Full inventory render so Compose/nginx match every registered service.
        self.render()

    def render(self) -> None:
        from .render import StackRenderer

        StackRenderer(self.stack).render()
        say("rendered .generated/ from inventory + service contracts")

    def start(self) -> None:
        running = self.docker.running_services()
        if running:
            joined = ", ".join(running)
            raise RuntimeError(
                f"stack already running ({joined}). "
                "Refusing to rebuild/reload everything — "
                "run `uv run raft down` first, "
                "or `uv run raft redeploy <app|router>` for a targeted update."
            )
        logger.info("syncing service sources from inventory")
        self.sync()
        logger.info("starting stack")
        self.docker.start_stack()
        logger.info("waiting for public Host checks")
        for app in self.stack.apps:
            wait_until(
                f"Host {app.public_host}",
                lambda a=app: self.http.public_host_ok(a),
                timeout=45,
                interval=1.0,
            )
        say("stack is up")
        say("redeploy with: uv run raft redeploy <app>")

    def stop(self) -> None:
        running = self.docker.running_services()
        if not running:
            say("stack already stopped")
            for app in self.stack.apps:
                self.docker.remove_container(app.tmp_container)
            return
        logger.info("stopping stack (%s)", ", ".join(running))
        self.docker.stop_stack()
        say("stack stopped")

    def redeploy(self, target: str) -> None:
        if target == self.stack.router:
            self.redeploy_router()
            return
        if target == self.stack.gate:
            raise RuntimeError(
                "refusing to redeploy `gate` — it is the stable public edge. "
                "Change gate only deliberately (`down`/`up`), not via redeploy."
            )
        self.redeploy_app(target)

    def redeploy_router(self) -> None:
        if self.stack.gate not in self.docker.running_services():
            raise RuntimeError("gate is not running — bring the stack up first")
        logger.info("recreating inner router (gate stays up)")
        self.docker.recreate_router()
        logger.info("waiting for public Host checks via gate")
        for app in self.stack.apps:
            wait_until(
                f"Host {app.public_host}",
                lambda a=app: self.http.public_host_ok(a),
                timeout=45,
                interval=1.0,
            )
        say("router redeployed")

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
                "ERROR during redeploy of %s; traffic may still be on tmp or "
                "previous upstream — inspect before retrying",
                app.name,
            )
            raise
        say(f"redeployed {app.name}")
