"""Signed cookie sessions for dashboard password auth."""

import hashlib
import hmac
import secrets
import time
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from raft.core.lifecycle.dashboard.password import DashboardPassword

_COOKIE = "raft_dash_session"
_CSRF_COOKIE = "raft_dash_csrf"
_TTL_SECONDS = 12 * 3600


class PasswordSessionAuth:
    """PBKDF2 verify + HMAC-signed session cookie + CSRF cookie."""

    def __init__(
        self,
        data_home: Path,
        *,
        users: Mapping[str, str],
    ) -> None:
        self._users = {str(k).strip().lower(): v for k, v in users.items() if k}
        self._password = DashboardPassword()
        self._secret = self._load_or_create_secret(data_home)

    @classmethod
    def from_hashes(
        cls,
        data_home: Path,
        *,
        password_hash: Optional[str] = None,
        users: Optional[Mapping[str, str]] = None,
    ) -> "PasswordSessionAuth":
        merged: Dict[str, str] = {}
        if users:
            merged.update(users)
        if password_hash and "admin" not in merged:
            merged["admin"] = password_hash
        return cls(data_home, users=merged)

    def login(
        self, password: str, *, username: Optional[str] = None
    ) -> Optional[tuple[str, str]]:
        """Return ``(session_cookie, csrf_cookie)`` or None on failure."""
        user = (username or "admin").strip().lower()
        encoded = self._users.get(user)
        if not encoded or not self._password.verify(password, encoded):
            return None
        csrf = secrets.token_urlsafe(24)
        exp = int(time.time()) + _TTL_SECONDS
        payload = f"2|{user}|{exp}|{csrf}"
        sig = self._sign(payload)
        return f"{payload}.{sig}", csrf

    def session_ok(self, cookie: Optional[str]) -> bool:
        return self._parse(cookie) is not None

    def username(self, cookie: Optional[str]) -> Optional[str]:
        parsed = self._parse(cookie)
        if parsed is None:
            return None
        return parsed[0]

    def csrf_ok(self, cookie: Optional[str], header: Optional[str]) -> bool:
        parsed = self._parse(cookie)
        if parsed is None or not header:
            return False
        return hmac.compare_digest(parsed[2], header)

    def cookie_name(self) -> str:
        return _COOKIE

    def csrf_cookie_name(self) -> str:
        return _CSRF_COOKIE

    def _parse(self, cookie: Optional[str]) -> Optional[Tuple[str, int, str]]:
        if not cookie or "." not in cookie:
            return None
        payload, sig = cookie.rsplit(".", 1)
        if not hmac.compare_digest(self._sign(payload), sig):
            return None
        parts = payload.split("|")
        if parts and parts[0] == "2" and len(parts) == 4:
            return self._parse_v2(parts)
        if parts and parts[0] == "1" and len(parts) == 3:
            return self._parse_v1(parts)
        return None

    def _parse_v2(self, parts: list[str]) -> Optional[Tuple[str, int, str]]:
        user = parts[1].strip().lower()
        try:
            exp = int(parts[2])
        except ValueError:
            return None
        if exp < int(time.time()) or user not in self._users:
            return None
        return user, exp, parts[3]

    def _parse_v1(self, parts: list[str]) -> Optional[Tuple[str, int, str]]:
        """Legacy shared-password sessions → subject ``admin``."""
        try:
            exp = int(parts[1])
        except ValueError:
            return None
        if exp < int(time.time()) or "admin" not in self._users:
            return None
        return "admin", exp, parts[2]

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
