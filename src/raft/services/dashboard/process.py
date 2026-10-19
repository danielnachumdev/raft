"""Always-on dashboard: app on loopback, nginx auth edge in front."""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.dashboard.proxy_nginx import (
    DEFAULT_APP_PORT,
    DashboardProxyNginx,
)

_CONF = Path("/tmp/raft-dashboard-nginx.conf")
_APP_WAIT_SECONDS = 120.0


class DashboardProcess:
    """Backend on loopback → wait ready → nginx edge → trap both processes."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack
        self._app: Optional[subprocess.Popen] = None
        self._nginx: Optional[subprocess.Popen] = None

    def run(self) -> None:
        cfg = SettingsLoader().load(self._stack.root).dashboard
        listen = self._listen_port(cfg.port)
        app_port = self._app_port()
        self._log(f"auth.mode={cfg.auth.mode} listen={listen} app={app_port}")
        self._write_nginx(cfg, listen=listen, app_port=app_port)
        self._app = self._start_app(app_port=app_port)
        self._wait_ready(app_port)
        self._nginx = self._start_nginx()
        self._install_signals()
        code = self._wait_either()
        self._shutdown()
        raise SystemExit(code)

    def _write_nginx(self, cfg, *, listen: int, app_port: int) -> None:
        text = DashboardProxyNginx().render(
            cfg, listen=listen, app_port=app_port
        )
        _CONF.write_text(text, encoding="utf-8")
        self._log(f"wrote {_CONF}")

    def _start_app(self, *, app_port: int) -> subprocess.Popen:
        self._log(f"starting uvicorn on 127.0.0.1:{app_port}")
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "raft.services.dashboard.app_server",
                str(app_port),
            ],
            env=os.environ.copy(),
        )

    def _start_nginx(self) -> subprocess.Popen:
        self._log(f"starting nginx on conf {_CONF}")
        return subprocess.Popen(
            ["nginx", "-c", str(_CONF), "-g", "daemon off;"]
        )

    def _wait_either(self) -> int:
        assert self._app is not None and self._nginx is not None
        while True:
            app_code = self._app.poll()
            nginx_code = self._nginx.poll()
            if app_code is not None:
                self._log(f"app exited code={app_code}")
                return int(app_code)
            if nginx_code is not None:
                self._log(f"nginx exited code={nginx_code}")
                return int(nginx_code)
            time.sleep(0.5)

    def _install_signals(self) -> None:
        def _handle(signum, _frame) -> None:
            self._log(f"signal {signum}")
            self._shutdown()
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT, _handle)

    def _shutdown(self) -> None:
        for proc in (self._nginx, self._app):
            if proc is None or proc.poll() is not None:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    @staticmethod
    def _wait_ready(port: int, *, timeout: float = _APP_WAIT_SECONDS) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with socket.socket() as sock:
                sock.settimeout(0.2)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    DashboardProcess._log(f"app ready on :{port}")
                    return
            time.sleep(0.1)
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

    @staticmethod
    def _log(msg: str) -> None:
        print(f"dashboard: {msg}", flush=True)
