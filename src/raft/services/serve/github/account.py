"""GitHub connected-account model for ``raft serve`` (public-safe views)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class GithubAccount:
    id: str
    login: str
    access_token: str
    mock: bool
    expires_at: float
    github_user_id: Optional[str] = None
    created_at: Optional[float] = None
    last_used_at: Optional[float] = None

    def is_expired(self, *, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def to_public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "login": self.login,
            "mock": self.mock,
            "expires_at": self.expires_at,
            "expired": self.is_expired(),
        }

    def to_storage(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "login": self.login,
            "access_token": self.access_token,
            "mock": self.mock,
            "expires_at": self.expires_at,
            "github_user_id": self.github_user_id,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    @staticmethod
    def from_raw(raw: Any) -> Optional["GithubAccount"]:
        if not isinstance(raw, dict):
            return None
        try:
            return GithubAccount(
                id=str(raw["id"]),
                login=str(raw["login"]),
                access_token=str(raw["access_token"]),
                mock=bool(raw.get("mock", False)),
                expires_at=float(raw["expires_at"]),
                github_user_id=_opt_str(raw.get("github_user_id")),
                created_at=_opt_float(raw.get("created_at")),
                last_used_at=_opt_float(raw.get("last_used_at")),
            )
        except (KeyError, TypeError, ValueError):
            return None


@dataclass
class GithubPendingOauth:
    state: str
    expires_at: float

    def is_expired(self, *, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def to_storage(self) -> dict[str, Any]:
        return {"state": self.state, "expires_at": self.expires_at}

    @staticmethod
    def from_raw(raw: Any) -> Optional["GithubPendingOauth"]:
        if not isinstance(raw, dict):
            return None
        try:
            return GithubPendingOauth(
                state=str(raw["state"]),
                expires_at=float(raw["expires_at"]),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)
