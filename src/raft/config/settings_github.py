"""Parse ``github:`` (serve OAuth / mock) from settings.yaml + env."""

from __future__ import annotations

import os
from typing import Any, Optional

from raft.errors.cta import OperatorError

from .settings_types import DEFAULT_GITHUB_SESSION_TTL_SECONDS, GithubServeConfig

_ENV_MOCK = "RAFT_GITHUB_MOCK"
_ENV_CLIENT_ID = "RAFT_GITHUB_CLIENT_ID"
_ENV_CLIENT_SECRET = "RAFT_GITHUB_CLIENT_SECRET"
_ENV_TTL = "RAFT_GITHUB_SESSION_TTL_SECONDS"


class GithubSettingsParser:
    """Resolve GitHub serve config: settings.yaml, then env overrides."""

    def parse(self, raw: Any) -> GithubServeConfig:
        base = self._from_mapping(raw)
        return self._apply_env(base)

    def _from_mapping(self, raw: Any) -> GithubServeConfig:
        if raw is None:
            return GithubServeConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml github must be a mapping.\n"
                "Fix: set github: {mock: true} or github: {clientId: …, clientSecret: …}",
                has_fix=False,
            )
        return GithubServeConfig(
            mock=bool(raw.get("mock", False)),
            client_id=self._opt_str(raw.get("clientId")),
            client_secret=self._opt_str(raw.get("clientSecret")),
            session_ttl_seconds=self._ttl(raw.get("sessionTtlSeconds")),
        )

    def _apply_env(self, base: GithubServeConfig) -> GithubServeConfig:
        mock = self._env_bool(_ENV_MOCK, base.mock)
        client_id = os.environ.get(_ENV_CLIENT_ID) or base.client_id
        client_secret = os.environ.get(_ENV_CLIENT_SECRET) or base.client_secret
        ttl = self._env_ttl(base.session_ttl_seconds)
        return GithubServeConfig(
            mock=mock,
            client_id=self._opt_str(client_id),
            client_secret=self._opt_str(client_secret),
            session_ttl_seconds=ttl,
        )

    @staticmethod
    def _ttl(raw: Any) -> int:
        if raw is None:
            return DEFAULT_GITHUB_SESSION_TTL_SECONDS
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise OperatorError(
                f"settings.yaml github.sessionTtlSeconds must be an integer, "
                f"got {raw!r}.\n"
                f"Fix: set github.sessionTtlSeconds in ~/.raft/settings.yaml",
                has_fix=False,
            ) from exc
        if value < 60:
            raise OperatorError(
                f"settings.yaml github.sessionTtlSeconds must be >= 60, got {value}.\n"
                f"Fix: set github.sessionTtlSeconds to at least 60",
                has_fix=False,
            )
        return value

    @staticmethod
    def _env_ttl(default: int) -> int:
        raw = os.environ.get(_ENV_TTL)
        if raw is None or not str(raw).strip():
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise OperatorError(
                f"{_ENV_TTL} must be an integer, got {raw!r}.\n"
                f"Fix: export {_ENV_TTL}=3600",
                has_fix=False,
            ) from exc
        if value < 60:
            raise OperatorError(
                f"{_ENV_TTL} must be >= 60, got {value}.\n"
                f"Fix: export {_ENV_TTL}=3600",
                has_fix=False,
            )
        return value

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None or not str(raw).strip():
            return default
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _opt_str(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None
