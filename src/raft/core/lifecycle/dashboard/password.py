"""PBKDF2 password hashing for dashboard password auth (stdlib only)."""

import hashlib
import hmac
import secrets
from typing import Optional

_PREFIX = "pbkdf2_sha256"
_ITERATIONS = 260000
_SALT_BYTES = 16


class DashboardPassword:
    """Hash and verify operator dashboard passwords."""

    def hash(self, password: str) -> str:
        salt = secrets.token_hex(_SALT_BYTES)
        digest = self._digest(password, salt=salt, iterations=_ITERATIONS)
        return f"{_PREFIX}${_ITERATIONS}${salt}${digest}"

    def verify(self, password: str, encoded: Optional[str]) -> bool:
        if not encoded or not password:
            return False
        parts = encoded.split("$")
        if len(parts) != 4 or parts[0] != _PREFIX:
            return False
        try:
            iterations = int(parts[1])
        except ValueError:
            return False
        expected = self._digest(password, salt=parts[2], iterations=iterations)
        return hmac.compare_digest(expected, parts[3])

    @staticmethod
    def _digest(password: str, *, salt: str, iterations: int) -> str:
        raw = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return raw.hex()
