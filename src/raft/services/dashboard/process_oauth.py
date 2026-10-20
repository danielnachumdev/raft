"""Start oauth2-proxy sidecar for dashboard ``auth.mode: oauth``."""

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.oauth_paths import OAUTH_PROXY_PORT
from raft.core.lifecycle.dashboard.oauth_proxy_cfg import DashboardOAuthProxyCfg

_CFG = Path("/tmp/raft-dashboard-oauth2-proxy.cfg")
_PING_WAIT = 30.0


class DashboardOAuthProxyProcess:
    """Write cfg + spawn oauth2-proxy on loopback."""

    def start(self, cfg: DashboardConfig) -> subprocess.Popen:
        if not self._binary():
            raise OperatorError(
                "oauth2-proxy binary missing in dashboard image.\n"
                "Fix: rebuild raft-dashboard (Dockerfile installs oauth2-proxy)",
                has_fix=False,
            )
        self._require_env()
        text = DashboardOAuthProxyCfg().render(cfg)
        _CFG.write_text(text, encoding="utf-8")
        self._log(f"wrote {_CFG}")
        proc = subprocess.Popen(
            ["oauth2-proxy", f"--config={_CFG}"],
            env=os.environ.copy(),
        )
        self._wait_ping()
        return proc

    @staticmethod
    def _require_env() -> None:
        missing = [
            key
            for key in (
                "OAUTH2_PROXY_CLIENT_ID",
                "OAUTH2_PROXY_CLIENT_SECRET",
                "OAUTH2_PROXY_COOKIE_SECRET",
                "OAUTH2_PROXY_REDIRECT_URL",
            )
            if not (os.environ.get(key) or "").strip()
        ]
        if missing:
            raise OperatorError(
                "dashboard oauth missing env: "
                + ", ".join(missing)
                + ".\nFix: fill host/secrets/dashboard/oauth.env and recreate",
                has_fix=False,
            )

    @staticmethod
    def _binary() -> Optional[str]:
        from shutil import which

        return which("oauth2-proxy")

    @staticmethod
    def _wait_ping(*, timeout: float = _PING_WAIT) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with socket.socket() as sock:
                sock.settimeout(0.2)
                if sock.connect_ex(("127.0.0.1", OAUTH_PROXY_PORT)) == 0:
                    DashboardOAuthProxyProcess._log(
                        f"oauth2-proxy ready on :{OAUTH_PROXY_PORT}"
                    )
                    return
            time.sleep(0.1)
        raise RuntimeError(
            f"oauth2-proxy did not listen on {OAUTH_PROXY_PORT}"
        )

    @staticmethod
    def _log(msg: str) -> None:
        print(f"dashboard: {msg}", flush=True)
