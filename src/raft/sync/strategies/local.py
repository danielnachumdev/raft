"""LocalSyncStrategy — verify an on-disk App tree exists."""

import logging

from ...errors.cta import OperatorError
from ...models.app import App
from ..context import SyncContext
from ..strategy import SyncStrategy

logger = logging.getLogger(__name__)


class LocalSyncStrategy(SyncStrategy):
    """No clone/pull; require ``spec.path`` to already exist under the data home."""

    @property
    def type_id(self) -> str:
        return "local"

    def sync(self, app: App, ctx: SyncContext) -> None:
        dest = app.abs_path(ctx.stack.root)
        if not dest.is_dir():
            raise OperatorError(
                f"local app path missing: {dest}\n"
                f"Fix: create/copy the tree under {app.path}, or change "
                f"spec.source / re-apply the App"
            )
        logger.info("sync %s: local (%s)", app.name, app.path)
