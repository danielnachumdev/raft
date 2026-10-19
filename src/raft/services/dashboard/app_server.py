"""Uvicorn-only dashboard app (loopback). Supervised by ``DashboardProcess``."""

import os
import sys
from typing import List, Optional

import uvicorn

from raft.core.core.config.paths import RaftHome
from raft.core.core.models.stack import Stack
from raft.services.serve.http import ServeAppFactory
from raft.services.serve.service import DEFAULT_SERVE_PORT


def main(argv: Optional[List[str]] = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    app_port = int(args[0]) if args else _env_port("RAFT_DASHBOARD_APP_PORT", 18787)
    listen = _env_port("RAFT_SERVE_PORT", DEFAULT_SERVE_PORT)
    stack = Stack.load_apps(RaftHome().resolve())
    app = ServeAppFactory(stack, port=listen).create()
    uvicorn.run(app, host="127.0.0.1", port=app_port, log_level="warning")


def _env_port(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    return int(raw) if raw.isdigit() else default


if __name__ == "__main__":  # pragma: no cover
    main()
