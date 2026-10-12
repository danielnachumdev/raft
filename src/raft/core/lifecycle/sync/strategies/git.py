"""GitSyncStrategy — clone/fetch and detach at the wanted ref."""

from raft.core.core.models.app import App
from ..context import SyncContext
from ..strategy import SyncStrategy


class GitSyncStrategy(SyncStrategy):
    """Git-backed App: checkout under ``apps/`` and pin SHA in ``deploy/``."""

    @property
    def type_id(self) -> str:
        return "git"

    def sync(self, app: App, ctx: SyncContext) -> None:
        assert app.repo
        dest = app.abs_path(ctx.stack.root)
        clone_url = ctx.auth.effective_clone_url(app)
        wanted = ctx.wanted_ref(app)
        sha = ctx.checkout.sync(
            app,
            dest,
            clone_url,
            wanted=wanted,
            force=ctx.force,
        )
        ctx.refs.write_git(app, sha, wanted)
