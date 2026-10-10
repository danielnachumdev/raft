"""SeamlessDeployment — dual-run ``*_tmp`` cutover when live; single start when down."""

from __future__ import annotations

import logging

from ..cutover import DEPLOY_CUTOVER, CutoverSession
from .method import DeploymentContext, DeploymentMethod

logger = logging.getLogger(__name__)


class SeamlessDeployment(DeploymentMethod):
    """Default: side-by-side tmp cutover when a live replica is serving."""

    @property
    def type_id(self) -> str:
        return "seamless"

    def deploy_when_up(self, ctx: DeploymentContext) -> None:
        self._sync(ctx)
        session = self._session(ctx)
        logger.info("redeploy cutover for %s (%s)", ctx.app.name, ctx.app.public_host)
        self._run_cutover(session, ctx.app.name)
        ctx.support.finish_app_deploy(ctx.app, done="redeployed")

    def deploy_when_down(self, ctx: DeploymentContext) -> None:
        ctx.support.deploy_single_generation(
            ctx.app,
            ref_override=ctx.ref_override,
            force_sync=ctx.force_sync,
            done=ctx.done,
        )

    def _sync(self, ctx: DeploymentContext) -> None:
        logger.info("syncing %s before cutover", ctx.app.name)
        ctx.support.sync(
            [ctx.app.name], ref_override=ctx.ref_override, force=ctx.force_sync
        )

    def _session(self, ctx: DeploymentContext) -> CutoverSession:
        orch = ctx.support
        return CutoverSession(
            stack=orch.stack,
            app=ctx.app,
            docker=orch.docker,
            nginx=orch.nginx,
            http=orch.http,
        )

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
