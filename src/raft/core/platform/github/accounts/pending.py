"""Pending OAuth state for serve GitHub login."""

import time
from dataclasses import dataclass
from typing import Any, Optional


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
