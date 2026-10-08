"""Short-lived GitHub session file under ``state/serve/`` (mode 0600)."""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

SESSION_FILENAME = "github-session.json"
SESSION_DIR = Path("state") / "serve"


@dataclass
class GithubSession:
    access_token: str
    login: str
    mock: bool
    expires_at: float
    state: Optional[str] = None

    def is_expired(self, *, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def to_public(self) -> dict[str, Any]:
        return {
            "authenticated": True,
            "login": self.login,
            "mock": self.mock,
            "expires_at": self.expires_at,
        }


class GithubSessionStore:
    """Persists one serve-process GitHub session; never world-readable."""

    def __init__(self, data_home: Path) -> None:
        self._path = data_home / SESSION_DIR / SESSION_FILENAME

    def load(self) -> Optional[GithubSession]:
        if not self._path.is_file():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.clear()
            return None
        session = self._from_raw(raw)
        if session is None or session.is_expired():
            self.clear()
            return None
        return session

    def save(self, session: GithubSession) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(session), indent=2) + "\n"
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload.encode("utf-8"))
        finally:
            os.close(fd)
        os.replace(tmp, self._path)
        os.chmod(self._path, 0o600)

    def clear(self) -> None:
        if self._path.is_file():
            self._path.unlink(missing_ok=True)

    def mint_oauth_state(self) -> str:
        return secrets.token_urlsafe(24)

    @staticmethod
    def _from_raw(raw: Any) -> Optional[GithubSession]:
        if not isinstance(raw, dict):
            return None
        try:
            return GithubSession(
                access_token=str(raw["access_token"]),
                login=str(raw["login"]),
                mock=bool(raw.get("mock", False)),
                expires_at=float(raw["expires_at"]),
                state=raw.get("state"),
            )
        except (KeyError, TypeError, ValueError):
            return None
