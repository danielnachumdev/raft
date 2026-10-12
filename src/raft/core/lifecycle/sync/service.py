"""SourceSync — refresh App sources under the data home."""

from typing import Optional

from raft.core.platform.adapters.shell import Shell
from raft.core.platform.auth import GitAuthManager
from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack

from .catalogs import SourceSyncCatalogs
from .context import SyncContext
from .docker_gateway import DockerGateway
from .git_checkout import GitCheckoutService
from .git_gateway import GitGateway
from .ref_state import RefStateWriter
from .registry import SourceSyncRegistry


class SourceSync:
    """Orchestrate per-App sync via ``spec.source`` strategies."""

    def __init__(
        self,
        stack: Stack,
        shell: Shell,
        registry: Optional[SourceSyncRegistry] = None,
    ) -> None:
        self.stack = stack
        self.sh = shell
        self.auth = GitAuthManager(stack)
        self._git = GitGateway(shell)
        self._docker = DockerGateway(shell)
        self._checkout = GitCheckoutService(self._git)
        self._refs = RefStateWriter(stack)
        self._registry = registry or SourceSyncCatalogs.default()

    def sync(
        self,
        apps: Optional[list[App]] = None,
        *,
        ref_override: Optional[str] = None,
        force: bool = False,
    ) -> None:
        targets = apps if apps is not None else list(self.stack.apps)
        for app in targets:
            self._sync_one(app, ref_override=ref_override, force=force)

    def _sync_one(
        self,
        app: App,
        *,
        ref_override: Optional[str],
        force: bool,
    ) -> None:
        ctx = SyncContext(
            stack=self.stack,
            auth=self.auth,
            git=self._git,
            docker=self._docker,
            checkout=self._checkout,
            refs=self._refs,
            ref_override=ref_override,
            force=force,
        )
        self._registry.get(app.source).sync(app, ctx)
