"""``python -m raft.services.dashboard`` — thin wrapper around Serve."""

import os

from raft.core.core.config.paths import RaftHome
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.models.stack import Stack
from raft.services.serve.service import DEFAULT_SERVE_PORT, Serve


def main() -> None:
    """Bind Serve using ``dashboard.port`` / ``RAFT_SERVE_PORT``.

    Uses ``Stack.load_apps`` (no ``RaftHomeBootstrap``) because Compose mounts
    ``RAFT_DATA_HOME`` read-only — same pattern as the controller.
    """
    stack = Stack.load_apps(RaftHome().resolve())
    port = _port(stack.root)
    Serve(stack).run(port=port)


def _port(data_home) -> int:
    env = os.environ.get("RAFT_SERVE_PORT")
    if env and str(env).strip().isdigit():
        return int(env)
    return SettingsLoader().load(data_home).dashboard.port or DEFAULT_SERVE_PORT


if __name__ == "__main__":  # pragma: no cover
    main()
