"""Always-on dashboard: in-container nginx (auth) + uvicorn (SPA/API)."""

import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import uvicorn

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.dashboard.proxy_nginx import (
    DEFAULT_APP_PORT,
    DashboardProxyNginx,
)
from raft.services.serve.http import ServeAppFactory

_CONF = Path("/tmp/raft-dashboard-nginx.conf")


class DashboardProcess:
    """Write nginx.conf, start the app on localhost, foreground nginx."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def run(self) -> None:
        cfg = SettingsLoader().load(self._stack.root).dashboard
        listen = self._listen_port(cfg.port)
        app_port = self._app_port()
        self._write_nginx(cfg, listen=listen, app_port=app_port)
        server = self._start_app(listen=listen, app_port=app_port)
        self._wait_ready(app_port)
        code = self._run_nginx()
        server.should_exit = True
        raise SystemExit(code)

    def _write_nginx(self, cfg, *, listen: int, app_port: int) -> None:
        text = DashboardProxyNginx().render(
            cfg, listen=listen, app_port=app_port
        )
        _CONF.write_text(text, encoding="utf-8")

    def _start_app(self, *, listen: int, app_port: int) -> uvicorn.Server:
        app = ServeAppFactory(self._stack, port=listen).create()
        config = uvicorn.Config(
            app, host="127.0.0.1", port=app_port, log_level="warning"
        )
        server = uvicorn.Server(config)
        threading.Thread(target=server.run, daemon=True).start()
        return server

    @staticmethod
    def _run_nginx() -> int:
        proc = subprocess.Popen(
            ["nginx", "-c", str(_CONF), "-g", "daemon off;"]
        )
        return int(proc.wait())

    @staticmethod
    def _wait_ready(port: int, *, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with socket.socket() as sock:
                sock.settimeout(0.2)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    return
            time.sleep(0.05)
        raise RuntimeError(f"dashboard app did not listen on {port}")

    @staticmethod
    def _listen_port(settings_port: int) -> int:
        env = os.environ.get("RAFT_SERVE_PORT")
        if env and str(env).strip().isdigit():
            return int(env)
        return settings_port

    @staticmethod
    def _app_port() -> int:
        env = os.environ.get("RAFT_DASHBOARD_APP_PORT")
        if env and str(env).strip().isdigit():
            return int(env)
        return DEFAULT_APP_PORT
