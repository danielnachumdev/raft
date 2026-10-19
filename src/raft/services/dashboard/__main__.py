"""``python -m raft.services.dashboard`` — nginx auth proxy + Serve app."""

from raft.core.core.config.paths import RaftHome
from raft.core.core.models.stack import Stack

from .process import DashboardProcess


def main() -> None:
    """Load apps (RO data home) and run the in-container dashboard process.

    Uses ``Stack.load_apps`` (no ``RaftHomeBootstrap``) because Compose mounts
    ``RAFT_DATA_HOME`` read-only — same pattern as the controller.
    """
    stack = Stack.load_apps(RaftHome().resolve())
    DashboardProcess(stack).run()


if __name__ == "__main__":  # pragma: no cover
    main()
