"""Lock file paths under ``~/.raft/state/locks/``."""

from pathlib import Path

LOCKS_REL = Path("state") / "locks"
STACK_LOCK_NAME = "stack.lock"
NOTIFICATIONS_LOCK_NAME = "notifications.lock"
ACL_LOCK_NAME = "acl.lock"


class LockPaths:
    """Resolved flock paths for a raft data home."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def directory(self) -> Path:
        return self._root / LOCKS_REL

    def stack(self) -> Path:
        return self.directory() / STACK_LOCK_NAME

    def notifications(self) -> Path:
        return self.directory() / NOTIFICATIONS_LOCK_NAME

    def acl(self) -> Path:
        return self.directory() / ACL_LOCK_NAME

    def app(self, name: str) -> Path:
        safe = name.replace("/", "_").replace("\\", "_")
        return self.directory() / f"app-{safe}.lock"
