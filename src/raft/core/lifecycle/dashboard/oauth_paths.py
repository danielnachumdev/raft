"""Operator paths for dashboard OAuth secrets (under ``RAFT_DATA_HOME``)."""

from pathlib import Path

OAUTH_SECRETS_DIR = Path("secrets") / "dashboard"
OAUTH_ENV_REL = OAUTH_SECRETS_DIR / "oauth.env"
OAUTH_ALLOWLIST_REL = OAUTH_SECRETS_DIR / "oauth-allowlist.txt"
OAUTH_PROXY_PORT = 4180


class DashboardOAuthPaths:
    """Resolve OAuth secret files for a data home."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home

    def env_file(self) -> Path:
        return self._home / OAUTH_ENV_REL

    def allowlist_file(self, relative: str) -> Path:
        rel = Path(relative)
        if rel.is_absolute():
            return rel
        return self._home / rel

    def ensure_dir(self) -> Path:
        path = self._home / OAUTH_SECRETS_DIR
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
        return path
