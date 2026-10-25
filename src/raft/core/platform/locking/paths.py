"""Lock file paths under ``~/.raft/host/locks/``."""

from pathlib import Path

# Leaf constant — do not import via ``raft.core.core.config`` (loads settings →
# ``SettingsLock`` and cycles when locking is still initializing).
LOCKS_REL = Path("host") / "locks"
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

    def fifo(self, kind: str) -> Path:
        return self.directory() / f"fifo-{self._safe(kind)}"

    def fifo_seq(self, kind: str) -> Path:
        return self.fifo(kind) / "seq.lock"

    def fifo_next(self, kind: str) -> Path:
        return self.fifo(kind) / "next"

    def fifo_ticket(self, kind: str, ticket: int) -> Path:
        return self.fifo(kind) / f"ticket-{ticket:020d}"

    def host_job_flight(self, kind: str) -> Path:
        return self.directory() / f"host-job-{self._safe(kind)}.flight.json"

    @staticmethod
    def _safe(kind: str) -> str:
        return kind.replace("/", "_").replace("\\", "_")
