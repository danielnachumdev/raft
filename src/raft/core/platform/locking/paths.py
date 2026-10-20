"""Lock file paths under ``~/.raft/host/locks/``."""

from pathlib import Path

from raft.core.core.config.paths.constants import LOCKS_DIR

LOCKS_REL = LOCKS_DIR
STACK_LOCK_NAME = "stack.lock"
SETTINGS_LOCK_NAME = "settings.lock"
ACL_LOCK_NAME = "acl.lock"
ALERTS_LOCK_NAME = "alerts.lock"
DASHBOARD_LOCK_NAME = "dashboard.lock"


class LockPaths:
    """Resolved flock paths for a raft data home."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def directory(self) -> Path:
        return self._root / LOCKS_REL

    def stack(self) -> Path:
        return self.directory() / STACK_LOCK_NAME

    def settings(self) -> Path:
        return self.directory() / SETTINGS_LOCK_NAME

    def acl(self) -> Path:
        return self.directory() / ACL_LOCK_NAME

    def alerts(self) -> Path:
        return self.directory() / ALERTS_LOCK_NAME

    def dashboard(self) -> Path:
        return self.directory() / DASHBOARD_LOCK_NAME

    def app(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        return self.directory() / f"app-{safe}.lock"
