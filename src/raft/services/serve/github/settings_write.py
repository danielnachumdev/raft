"""Persist ``github:`` OAuth settings into ``~/.raft/settings.yaml`` at runtime."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from raft.config.paths import settings_path
from raft.config.settings import load_config
from raft.config.settings_types import GithubServeConfig
from raft.errors.cta import OperatorError

GITHUB_OAUTH_APP_URL = "https://github.com/settings/applications/new"
SETUP_DOCS_URL = (
    "https://github.com/danielnachumdev/raft/blob/main/docs/serve-github-deploy.md"
)


class GithubSettingsWriter:
    """Merge GitHub serve OAuth fields into operator settings and reload."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._path = settings_path(data_home)

    def public_status(self, *, port: int) -> Dict[str, Any]:
        cfg = load_config(self._home).github
        return {
            "oauth_configured": self.oauth_ready(cfg),
            "mock": cfg.mock,
            "client_id_set": bool(cfg.client_id),
            "callback_url": f"http://127.0.0.1:{port}/api/github/callback",
            "oauth_app_url": GITHUB_OAUTH_APP_URL,
            "docs_url": SETUP_DOCS_URL,
            "settings_path": str(self._path),
        }

    def save(
        self,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        mock: Optional[bool] = None,
    ) -> GithubServeConfig:
        patch = self._validated_patch(
            client_id=client_id, client_secret=client_secret, mock=mock
        )
        self._merge_github(patch)
        return load_config(self._home).github

    @staticmethod
    def oauth_ready(cfg: GithubServeConfig) -> bool:
        return bool(cfg.mock or (cfg.client_id and cfg.client_secret))

    def _validated_patch(
        self,
        *,
        client_id: Optional[str],
        client_secret: Optional[str],
        mock: Optional[bool],
    ) -> Dict[str, Any]:
        cid = self._opt(client_id)
        secret = self._opt(client_secret)
        use_mock = bool(mock) if mock is not None else False
        if use_mock:
            return {"mock": True}
        if not cid or not secret:
            raise OperatorError(
                "GitHub OAuth needs clientId and clientSecret "
                "(or enable mock mode).\n"
                "Fix: paste both values from your GitHub OAuth App, "
                f"or see {SETUP_DOCS_URL}",
                has_fix=False,
            )
        return {"mock": False, "clientId": cid, "clientSecret": secret}

    def _merge_github(self, patch: Mapping[str, Any]) -> None:
        data = self._load_root()
        github = data.get("github")
        if not isinstance(github, dict):
            github = {}
        merged = dict(github)
        merged.update(patch)
        data["github"] = merged
        self._write_root(data)

    def _load_root(self) -> Dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot update settings.yaml: {self._path}\n"
                f"Fix: repair ~/.raft/settings.yaml then retry from serve",
                has_fix=False,
            ) from exc
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml must be a YAML mapping.\n"
                "Fix: repair ~/.raft/settings.yaml",
                has_fix=False,
            )
        return raw

    def _write_root(self, data: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(dict(data), sort_keys=False)
        self._path.write_text(text, encoding="utf-8")
        os.chmod(self._path, 0o600)

    @staticmethod
    def _opt(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None
