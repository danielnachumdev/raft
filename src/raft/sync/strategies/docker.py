"""DockerSyncStrategy — optional git manifest tree + image pull/pin."""

import logging
from pathlib import Path
from typing import Optional

from ...errors.checked import CheckedCommands
from ...models.app import App
from ..context import SyncContext
from ..strategy import SyncStrategy

logger = logging.getLogger(__name__)


class DockerSyncStrategy(SyncStrategy):
    """Docker-backed App: pull ``image:ref``, retag compose pin, record digest."""

    @property
    def type_id(self) -> str:
        return "docker"

    def sync(self, app: App, ctx: SyncContext) -> None:
        dest = app.abs_path(ctx.stack.root)
        if app.repo:
            self._sync_manifest_git(app, dest, ctx)
        wanted = ctx.wanted_ref(app)
        pull_ref = app.image_ref(wanted)
        pin = app.compose_pin_image
        logger.info("sync %s: docker pull %s", app.name, pull_ref)
        self._pull(ctx, pull_ref, app=app.name, repo=app.repo)
        self._retarget_pin(ctx, app.name, pull_ref, pin)
        digest = ctx.docker.inspect_digest(pin)
        ctx.refs.write_docker(app, digest, pull_ref, pin, wanted)
        logger.info("sync %s: ready at %s", app.name, digest[:64])

    @staticmethod
    def _sync_manifest_git(app: App, dest: Path, ctx: SyncContext) -> None:
        clone_url = ctx.auth.effective_clone_url(app)
        ctx.checkout.sync(
            app,
            dest,
            clone_url,
            wanted=ctx.wanted_ref(app),
            force=ctx.force,
        )

    @staticmethod
    def _pull(
        ctx: SyncContext,
        image: str,
        *,
        app: Optional[str],
        repo: Optional[str],
    ) -> None:
        result = ctx.docker.pull(image)
        if result.returncode == 0:
            return
        detail = (result.stderr or result.stdout or "").strip()
        CheckedCommands.raise_for_docker_pull_failure(image, detail=detail, app=app, repo=repo)

    @staticmethod
    def _retarget_pin(
        ctx: SyncContext, app_name: str, pull_ref: str, pin: str
    ) -> None:
        if pull_ref == pin:
            return
        logger.info(
            "sync %s: tag %s -> %s (compose pin)", app_name, pull_ref, pin
        )
        ctx.docker.tag(pull_ref, pin)
