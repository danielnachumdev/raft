"""Read/write ``secrets/dashboard/oauth.env`` (0600)."""

import os
import secrets
from pathlib import Path
from typing import Dict

from raft.core.core.config.settings.dashboard_config import (
    DEFAULT_OAUTH_REDIRECT_PATH,
    DashboardConfig,
)

from .oauth_paths import DashboardOAuthPaths

REQUIRED_OAUTH_ENV = (
    "OAUTH2_PROXY_CLIENT_ID",
    "OAUTH2_PROXY_CLIENT_SECRET",
    "OAUTH2_PROXY_COOKIE_SECRET",
    "OAUTH2_PROXY_REDIRECT_URL",
)


class DashboardOAuthEnv:
    """Template + parse oauth2-proxy environment file."""

    def __init__(self, data_home: Path) -> None:
        self._paths = DashboardOAuthPaths(data_home)

    def path(self) -> Path:
        return self._paths.env_file()

    def load(self) -> Dict[str, str]:
        path = self.path()
        if not path.is_file():
            return {}
        return self._parse(path.read_text(encoding="utf-8"))

    def write_template(self, cfg: DashboardConfig) -> Path:
        self._paths.ensure_dir()
        path = self.path()
        existing = self.load()
        cookie = existing.get("OAUTH2_PROXY_COOKIE_SECRET") or secrets.token_urlsafe(32)
        redirect = existing.get("OAUTH2_PROXY_REDIRECT_URL") or self.redirect_url(cfg)
        lines = [
            "# Dashboard OAuth (oauth2-proxy). Mode 0600. Do not commit.",
            f"OAUTH2_PROXY_CLIENT_ID={existing.get('OAUTH2_PROXY_CLIENT_ID', '')}",
            f"OAUTH2_PROXY_CLIENT_SECRET="
            f"{existing.get('OAUTH2_PROXY_CLIENT_SECRET', '')}",
            f"OAUTH2_PROXY_COOKIE_SECRET={cookie}",
            f"OAUTH2_PROXY_REDIRECT_URL={redirect}",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        os.chmod(path, 0o600)
        return path

    def secrets_present(self) -> bool:
        values = self.load()
        return all(values.get(key) for key in REQUIRED_OAUTH_ENV)

    @staticmethod
    def redirect_url(cfg: DashboardConfig) -> str:
        host = (cfg.public_host or "ops.example.com").strip()
        path = cfg.auth.oauth.redirect_path or DEFAULT_OAUTH_REDIRECT_PATH
        if not path.startswith("/"):
            path = f"/{path}"
        scheme = "https" if cfg.tls in {"origin", "acme"} else "http"
        return f"{scheme}://{host}{path}"

    @staticmethod
    def _parse(text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for line in text.splitlines():
            item = line.strip()
            if not item or item.startswith("#") or "=" not in item:
                continue
            key, _, value = item.partition("=")
            out[key.strip()] = value.strip().strip('"').strip("'")
        return out
