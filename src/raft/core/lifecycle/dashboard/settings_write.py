"""Persist ``dashboard:`` into ``~/.raft/host/settings.yaml``."""

from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from raft.core.core.config.paths import RaftHome
from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import DashboardLock

from .oauth_ready import DashboardOAuthReady
from .password import DashboardPassword
from .settings_serde import DashboardSettingsSerde


class DashboardSettingsWriter:
    """Merge dashboard settings under ``dashboard.lock``."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._path = RaftHome().settings_path(data_home)
        self._parser = DashboardSettingsParser()
        self._password = DashboardPassword()
        self._oauth_ready = DashboardOAuthReady(data_home)
        self._serde = DashboardSettingsSerde(self._path)

    def load(self) -> DashboardConfig:
        return SettingsLoader().load(self._home).dashboard

    def status_public(self) -> Dict[str, Any]:
        cfg = self.load()
        auth = self._serde.auth_public(cfg.auth)
        if cfg.auth.mode == "oauth":
            auth["oauth"] = self._oauth_ready.status_public(cfg)
        return {
            "enabled": cfg.enabled,
            "port": cfg.port,
            "publicHost": cfg.public_host,
            "tls": cfg.tls,
            "auth": auth,
            "localUrl": f"http://127.0.0.1:{cfg.port}/",
            "publicUrl": self._serde.public_url(cfg),
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
            users=cfg.auth.users,
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
        raw = self._serde.to_raw(cfg)
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
                "Fix: set dashboard.auth.passwordHash in Settings "
                "(plaintext is hashed on save), set enabled: true, "
                "then raft render + raft up dashboard",
                has_fix=False,
            )
        if cfg.auth.mode == "oauth":
            self._oauth_ready.require_ready(cfg)

    @staticmethod
    def _require_password_length(password: str) -> None:
        if not password or len(password) < 8:
            raise OperatorError(
                "dashboard password must be at least 8 characters.\n"
                "Fix: set a longer password in Settings → Dashboard",
                has_fix=False,
            )

    def _persist(self, cfg: DashboardConfig) -> None:
        data = self._serde.load_root()
        data["dashboard"] = self._serde.to_raw(cfg)
        self._serde.write_root(data)