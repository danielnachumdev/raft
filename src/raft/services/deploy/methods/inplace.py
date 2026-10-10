"""InPlaceDeployment — stop then rebuild on the steady name (brief downtime OK)."""

from __future__ import annotations

import logging

from .method import DeploymentContext, DeploymentMethod

logger = logging.getLogger(__name__)


class InPlaceDeployment(DeploymentMethod):
    """Resource-focused: never run ``*_tmp`` beside the live generation."""

    @property
    def type_id(self) -> str:
        return "inplace"

    def deploy_when_up(self, ctx: DeploymentContext) -> None:
        logger.info("in-place deploy for %s (brief downtime)", ctx.app.name)
        self._sync(ctx)
        self._drop_tmp_if_any(ctx)
        self._stop_old(ctx)
        self._start_new(ctx)
        ctx.support.finish_app_deploy(ctx.app, done="redeployed")

    def deploy_when_down(self, ctx: DeploymentContext) -> None:
        ctx.support.deploy_single_generation(
            ctx.app,
            ref_override=ctx.ref_override,
            force_sync=ctx.force_sync,
            done=ctx.done,
        )

    def _sync(self, ctx: DeploymentContext) -> None:
        logger.info("syncing %s before in-place deploy", ctx.app.name)
        ctx.support.sync(
            [ctx.app.name], ref_override=ctx.ref_override, force=ctx.force_sync
        )

    def _drop_tmp_if_any(self, ctx: DeploymentContext) -> None:
        ctx.support.docker.remove_container(ctx.app.tmp_container)

    def _stop_old(self, ctx: DeploymentContext) -> None:
        logger.info("stop %s before in-place rebuild", ctx.app.compose_id)
        ctx.support.docker.stop_service(ctx.app.compose_id)

    def _start_new(self, ctx: DeploymentContext) -> None:
        self._rebuild_steady(ctx)
        ctx.support.nginx.point_at(ctx.app, ctx.app.compose_id)
        ctx.support.docker.nginx_test_and_reload()
        ctx.support._wait_app_ready(ctx.app)

    def _rebuild_steady(self, ctx: DeploymentContext) -> None:
        app = ctx.app
        if app.source == "docker":
            pull_ref = app.image_ref(self._wanted_tag(ctx))
            logger.info("pull/recreate steady %s (%s)", app.name, pull_ref)
            ctx.support.docker.recreate_pulled_service(app, pull_ref=pull_ref)
            return
        logger.info("rebuild steady service %s (new code)", app.name)
        ctx.support.docker.rebuild_service(app.compose_id)

    def _wanted_tag(self, ctx: DeploymentContext) -> str:
        state = ctx.support.stack.ref_state_file(ctx.app)
        try:
            lines = state.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return ctx.app.ref
        return self._tag_from_lines(lines, ctx.app.ref)

    @staticmethod
    def _tag_from_lines(lines: list[str], fallback: str) -> str:
        for line in lines:
            if line.startswith("# requested:"):
                parsed = line.split(":", 1)[1].strip()
                return parsed or fallback
        return fallback
