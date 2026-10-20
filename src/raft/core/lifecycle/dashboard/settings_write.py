"""Persist ``dashboard:`` into ``~/.raft/host/settings.yaml``."""

import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from raft.core.core.config.paths import RaftHome
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
    DashboardOAuthConfig,
)
from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import DashboardLock

from .password import DashboardPassword


class DashboardSettingsWriter:
    """Merge dashboard settings under ``dashboard.lock``."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._path = RaftHome().settings_path(data_home)
        self._parser = DashboardSettingsParser()
        self._password = DashboardPassword()

    def load(self) -> DashboardConfig:
        return SettingsLoader().load(self._home).dashboard

    def status_public(self) -> Dict[str, Any]:
        cfg = self.load()
        from .oauth_ops import DashboardOAuthOps

        auth = self._auth_public(cfg.auth)
        if cfg.auth.mode == "oauth":
            auth["oauth"] = DashboardOAuthOps(self._home).status_public(cfg)
        return {
            "enabled": cfg.enabled,
            "port": cfg.port,
            "publicHost": cfg.public_host,
            "tls": cfg.tls,
            "auth": auth,
            "localUrl": f"http://127.0.0.1:{cfg.port}/",
            "publicUrl": self._public_url(cfg),
        }

    def replace(self, cfg: DashboardConfig) -> None:
        """Persist a full dashboard config (caller holds ``dashboard.lock``)."""
        self._persist(cfg)

    def enable(self, **kwargs: Optional[str]) -> DashboardConfig:
        with DashboardLock(self._home):
            next_cfg = self._merge_enable(self.load(), **kwargs)
            self._require_ready(next_cfg)
            self._persist(next_cfg)
            return next_cfg

    def disable(self) -> DashboardConfig:
        with DashboardLock(self._home):
            cfg = self.load()
            next_cfg = DashboardConfig(
                enabled=False,
                port=cfg.port,
                public_host=cfg.public_host,
                tls=cfg.tls,
                auth=cfg.auth,
            )
            self._persist(next_cfg)
            return next_cfg

    def set_password(self, password: str) -> DashboardConfig:
        self._require_password_length(password)
        with DashboardLock(self._home):
            cfg = self.load()
            next_cfg = self._with_password(cfg, password)
            self._persist(next_cfg)
            return next_cfg

    def _with_password(self, cfg: DashboardConfig, password: str) -> DashboardConfig:
        mode = "password" if cfg.auth.mode == "none" else cfg.auth.mode
        auth = DashboardAuthConfig(
            mode=mode,
            password_hash=self._password.hash(password),
            verify_url=cfg.auth.verify_url,
            sign_in_url=cfg.auth.sign_in_url,
            identity_header=cfg.auth.identity_header,
            oauth=cfg.auth.oauth,
        )
        return DashboardConfig(
            enabled=cfg.enabled,
            port=cfg.port,
            public_host=cfg.public_host,
            tls=cfg.tls,
            auth=auth,
        )

    def _merge_enable(self, cfg: DashboardConfig, **kwargs: Optional[str]) -> DashboardConfig:
        raw = self._to_raw(cfg)
        raw["enabled"] = True
        self._apply_enable_kwargs(raw, kwargs)
        return self._parser.parse(raw)

    def _apply_enable_kwargs(self, raw: dict, kwargs: Mapping[str, Optional[str]]) -> None:
        if "public_host" in kwargs:
            self._set_public_host(raw, kwargs["public_host"])
        if kwargs.get("tls") is not None:
            raw["tls"] = kwargs["tls"]
        auth = dict(raw.get("auth") or {})
        self._set_auth_field(auth, kwargs, "auth_mode", "mode")
        self._set_auth_field(auth, kwargs, "verify_url", "verifyUrl")
        self._set_auth_field(auth, kwargs, "sign_in_url", "signInUrl")
        self._apply_oauth_kwargs(auth, kwargs)
        raw["auth"] = auth

    @staticmethod
    def _apply_oauth_kwargs(
        auth: dict, kwargs: Mapping[str, Optional[str]]
    ) -> None:
        if (
            kwargs.get("oauth_provider") is None
            and kwargs.get("oauth_issuer_url") is None
        ):
            return
        oauth = dict(auth.get("oauth") or {})
        if kwargs.get("oauth_provider") is not None:
            oauth["provider"] = kwargs["oauth_provider"]
        if kwargs.get("oauth_issuer_url") is not None:
            oauth["issuerUrl"] = kwargs["oauth_issuer_url"]
        auth["oauth"] = oauth

    @staticmethod
    def _set_public_host(raw: dict, value: Optional[str]) -> None:
        if value:
            raw["publicHost"] = value
        else:
            raw.pop("publicHost", None)

    @staticmethod
    def _set_auth_field(
        auth: dict, kwargs: Mapping[str, Optional[str]], key: str, field: str
    ) -> None:
        if kwargs.get(key) is not None:
            auth[field] = kwargs[key]

    def _require_ready(self, cfg: DashboardConfig) -> None:
        if cfg.requires_password_hash() and not cfg.auth.password_hash:
            raise OperatorError(
                "dashboard public password auth requires a password.\n"
                "Fix: raft dashboard set-password, then raft dashboard enable",
                has_fix=False,
            )
        if cfg.auth.mode == "oauth":
            from .oauth_ops import DashboardOAuthOps

            DashboardOAuthOps(self._home).require_ready(cfg)

    @staticmethod
    def _require_password_length(password: str) -> None:
        if not password or len(password) < 8:
            raise OperatorError(
                "dashboard password must be at least 8 characters.\n"
                "Fix: raft dashboard set-password with a longer secret",
                has_fix=False,
            )

    def _persist(self, cfg: DashboardConfig) -> None:
        data = self._load_root()
        data["dashboard"] = self._to_raw(cfg)
        self._write_root(data)

    def _to_raw(self, cfg: DashboardConfig) -> Dict[str, Any]:
        auth = self._auth_raw(cfg.auth)
        raw: Dict[str, Any] = {
            "enabled": cfg.enabled,
            "port": cfg.port,
            "tls": cfg.tls,
            "auth": auth,
        }
        if cfg.public_host:
            raw["publicHost"] = cfg.public_host
        return raw

    @staticmethod
    def _auth_raw(auth: DashboardAuthConfig) -> Dict[str, Any]:
        out: Dict[str, Any] = {"mode": auth.mode}
        if auth.password_hash:
            out["passwordHash"] = auth.password_hash
        if auth.verify_url:
            out["verifyUrl"] = auth.verify_url
        if auth.sign_in_url:
            out["signInUrl"] = auth.sign_in_url
        if auth.identity_header:
            out["identityHeader"] = auth.identity_header
        out["oauth"] = DashboardSettingsWriter._oauth_raw(auth.oauth)
        return out

    @staticmethod
    def _oauth_raw(oauth: DashboardOAuthConfig) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "provider": oauth.provider,
            "redirectPath": oauth.redirect_path,
            "allowlistFile": oauth.allowlist_file,
        }
        if oauth.issuer_url:
            out["issuerUrl"] = oauth.issuer_url
        return out

    @staticmethod
    def _auth_public(auth: DashboardAuthConfig) -> Dict[str, Any]:
        return {
            "mode": auth.mode,
            "hasPasswordHash": bool(auth.password_hash),
            "verifyUrl": auth.verify_url,
            "signInUrl": auth.sign_in_url,
            "identityHeader": auth.identity_header,
        }

    @staticmethod
    def _public_url(cfg: DashboardConfig) -> Optional[str]:
        if not cfg.is_public():
            return None
        scheme = "https" if cfg.tls in {"origin", "acme"} else "http"
        return f"{scheme}://{cfg.public_host}/"

    def _load_root(self) -> Dict[str, Any]:
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

    def _write_root(self, data: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.safe_dump(dict(data), sort_keys=False)
        self._path.write_text(text, encoding="utf-8")
        os.chmod(self._path, 0o600)
