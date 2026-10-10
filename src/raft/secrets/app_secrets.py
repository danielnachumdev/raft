"""Per-App secret layout under ``~/.raft/secrets/<app>/``."""

from __future__ import annotations

import os
from pathlib import Path

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
        return self._home / SECRETS_DIRNAME

    def app_dir(self, app_name: str) -> Path:
        return self.root() / app_name

    def env_file(self, app_name: str) -> Path:
        return self.app_dir(app_name) / ENV_FILENAME

    def ensure_root(self) -> Path:
        path = self.root()
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, APP_DIR_MODE)
        return path

    def ensure_app_dir(self, app_name: str) -> Path:
        self.ensure_root()
        path = self.app_dir(app_name)
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, APP_DIR_MODE)
        return path
