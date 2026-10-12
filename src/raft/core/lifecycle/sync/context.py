"""Per-sync inputs shared by SourceSync strategies."""

import os
from dataclasses import dataclass
from typing import Optional

from raft.core.platform.auth import GitAuthManager
from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack

from .docker_gateway import DockerGateway
from .git_checkout import GitCheckoutService
from .git_gateway import GitGateway
from .ref_state import RefStateWriter


@dataclass
class SyncContext:
    """Collaborators + flags for one sync pass over an App."""

    stack: Stack
    auth: GitAuthManager
    git: GitGateway
    docker: DockerGateway
    checkout: GitCheckoutService
    refs: RefStateWriter
    ref_override: Optional[str] = None
    force: bool = False

    def wanted_ref(self, app: App) -> str:
        return (self.ref_override or os.environ.get("VPS_SYNC_REF") or app.ref).strip()
