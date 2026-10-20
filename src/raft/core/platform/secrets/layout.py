"""Per-App secret layout under ``~/.raft/services/<app>/secrets/``."""

import os
from pathlib import Path

from raft.core.core.config.paths.service_paths import ServicePaths

SECRETS_DIRNAME = "secrets"
ENV_FILENAME = "env"
APP_DIR_MODE = 0o700
ENV_FILE_MODE = 0o600


class AppSecretsLayout:
    """Recommended host paths for App ``spec.envFile`` secret material.

    Raft creates the directory scaffolding; operators write the ``env`` file.
    Gate/router must never mount these paths.
    """

    def __init__(self, home: Path) -> None:
        self._home = home

    def root(self) -> Path:
        """Parent of per-app secret dirs — ``services/`` (not a shared secrets tree)."""
        return self._home / "services"

    def app_dir(self, app_name: str) -> Path:
        return ServicePaths(self._home, app_name).secrets()

    def env_file(self, app_name: str) -> Path:
        return ServicePaths(self._home, app_name).secrets_env()

    def ensure_root(self) -> Path:
        path = self.root()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ensure_app_dir(self, app_name: str) -> Path:
        path = self.app_dir(app_name)
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, APP_DIR_MODE)
        return path
