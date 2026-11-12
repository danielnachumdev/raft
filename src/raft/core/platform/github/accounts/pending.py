"""Pending OAuth state for serve GitHub login."""

import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class GithubPendingOauth:
    state: str
    expires_at: float
    redirect_uri: Optional[str] = None

    def is_expired(self, *, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def to_storage(self) -> dict[str, Any]:
        out: dict[str, Any] = {"state": self.state, "expires_at": self.expires_at}
        if self.redirect_uri:
            out["redirect_uri"] = self.redirect_uri
        return out

    @staticmethod
    def from_raw(raw: Any) -> Optional["GithubPendingOauth"]:
        if not isinstance(raw, dict):
            return None
        try:
            redirect = raw.get("redirect_uri")
            return GithubPendingOauth(
                state=str(raw["state"]),
                expires_at=float(raw["expires_at"]),
                redirect_uri=str(redirect) if redirect else None,
            )
        except (KeyError, TypeError, ValueError):
            return None
