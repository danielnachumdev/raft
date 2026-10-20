"""Signed cookie sessions for dashboard password auth."""

import hashlib
import hmac
import secrets
import time
from pathlib import Path
from typing import Optional

from raft.core.lifecycle.dashboard.password import DashboardPassword

_COOKIE = "raft_dash_session"
_CSRF_COOKIE = "raft_dash_csrf"
_TTL_SECONDS = 12 * 3600


class PasswordSessionAuth:
    """PBKDF2 verify + HMAC-signed session cookie + CSRF cookie."""

    def __init__(self, data_home: Path, *, password_hash: str) -> None:
        self._hash = password_hash
        self._password = DashboardPassword()
        self._secret = self._load_or_create_secret(data_home)

    def login(self, password: str) -> Optional[tuple[str, str]]:
        """Return ``(session_cookie, csrf_cookie)`` or None on failure."""
        if not self._password.verify(password, self._hash):
            return None
        csrf = secrets.token_urlsafe(24)
        exp = int(time.time()) + _TTL_SECONDS
        payload = f"1|{exp}|{csrf}"
        sig = self._sign(payload)
        return f"{payload}.{sig}", csrf

    def session_ok(self, cookie: Optional[str]) -> bool:
        parsed = self._parse(cookie)
        return parsed is not None

    def csrf_ok(self, cookie: Optional[str], header: Optional[str]) -> bool:
        parsed = self._parse(cookie)
        if parsed is None:
            return False
        _, _, csrf = parsed
        if not header:
            return False
        return hmac.compare_digest(csrf, header)

    def cookie_name(self) -> str:
        return _COOKIE

    def csrf_cookie_name(self) -> str:
        return _CSRF_COOKIE

    def _parse(self, cookie: Optional[str]):
        if not cookie or "." not in cookie:
            return None
        payload, sig = cookie.rsplit(".", 1)
        if not hmac.compare_digest(self._sign(payload), sig):
            return None
        parts = payload.split("|")
        if len(parts) != 3 or parts[0] != "1":
            return None
        try:
            exp = int(parts[1])
        except ValueError:
            return None
        if exp < int(time.time()):
            return None
        return parts[0], exp, parts[2]

    def _sign(self, payload: str) -> str:
        return hmac.new(
            self._secret, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _load_or_create_secret(data_home: Path) -> bytes:
        path = data_home / "host" / "serve" / "dashboard-session.key"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            return path.read_bytes()
        raw = secrets.token_bytes(32)
        path.write_bytes(raw)
        path.chmod(0o600)
        return raw
