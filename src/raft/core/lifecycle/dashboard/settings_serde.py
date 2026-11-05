"""Serialize dashboard settings to/from host ``settings.yaml`` fragments."""

import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
    DashboardOAuthConfig,
)
from raft.core.core.errors.cta import OperatorError


class DashboardSettingsSerde:
    """YAML root load/write and dashboard config ↔ raw mapping."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def load_root(self) -> Dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            raw = yaml.safe_load(self._path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OperatorError(
                f"cannot update settings.yaml: {self._path}\n"
                f"Fix: repair ~/.raft/host/settings.yaml then retry",
                has_fix=False,
            ) from exc
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml must be a YAML mapping.\n"
                "Fix: repair ~/.raft/host/settings.yaml",
                has_fix=False,
            )
        return raw

    def write_root(self, data: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(dict(data), sort_keys=False)
        self._path.write_text(text, encoding="utf-8")
        os.chmod(self._path, 0o600)

    def to_raw(self, cfg: DashboardConfig) -> Dict[str, Any]:
        raw: Dict[str, Any] = {
            "enabled": cfg.enabled,
            "port": cfg.port,
            "tls": cfg.tls,
            "auth": self.auth_raw(cfg.auth),
        }
        if cfg.public_host:
            raw["publicHost"] = cfg.public_host
        return raw

    @staticmethod
    def auth_raw(auth: DashboardAuthConfig) -> Dict[str, Any]:
        out: Dict[str, Any] = {"mode": auth.mode}
        if auth.password_hash:
            out["passwordHash"] = auth.password_hash
        if auth.verify_url:
            out["verifyUrl"] = auth.verify_url
        if auth.sign_in_url:
            out["signInUrl"] = auth.sign_in_url
        if auth.identity_header:
            out["identityHeader"] = auth.identity_header
        out["oauth"] = DashboardSettingsSerde.oauth_raw(auth.oauth)
        return out

    @staticmethod
    def oauth_raw(oauth: DashboardOAuthConfig) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "provider": oauth.provider,
            "redirectPath": oauth.redirect_path,
            "allowlistFile": oauth.allowlist_file,
        }
        if oauth.issuer_url:
            out["issuerUrl"] = oauth.issuer_url
        return out

    @staticmethod
    def auth_public(auth: DashboardAuthConfig) -> Dict[str, Any]:
        return {
            "mode": auth.mode,
            "hasPasswordHash": bool(auth.password_hash),
            "verifyUrl": auth.verify_url,
            "signInUrl": auth.sign_in_url,
            "identityHeader": auth.identity_header,
        }

    @staticmethod
    def public_url(cfg: DashboardConfig) -> Optional[str]:
        if not cfg.is_public():
            return None
        scheme = "https" if cfg.tls in {"origin", "acme"} else "http"
        return f"{scheme}://{cfg.public_host}/"
